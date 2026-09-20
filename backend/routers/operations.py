from __future__ import annotations

import asyncio
import json
import re
import time
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.auth import get_current_user
from backend.capabilities import OPERATION_BY_ID, OPERATIONS, REACHY_APP_RESET, has_capability, operation_ineligibility
from backend.database import SessionLocal, get_db
from backend.models import Device, Job, DeviceReservation
from backend.schemas import OperationResponse, OperationRunRequest
from backend.services.ansible_runner import get_log_path, run_playbook, track_task, job_semaphore
from backend.services.job_results import get_job_results
from backend.services.execution_state import ExecutionConflict, reserve_devices, release_devices, request_fingerprint
from backend.services.device_discovery import (
    probe_reachy,
    reachy_request,
    reachy_websocket_url,
)

router = APIRouter(prefix="/api/v2/operations", tags=["operations"])


@router.get("", response_model=list[OperationResponse])
@router.get("/", response_model=list[OperationResponse], include_in_schema=False)
def list_operations(db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    devices = db.query(Device).order_by(Device.hostname).all()
    response = []
    reservations = {r.device_id: r.job_id for r in db.query(DeviceReservation).all()}
    def reason(device, operation):
        return f"Busy with job {reservations[device.id]}. Check Activity." if device.id in reservations else operation_ineligibility(device, operation)
    for operation in OPERATIONS:
        eligible = [device.id for device in devices if not reason(device, operation)]
        excluded = [{"id": d.id, "name": d.name, "reason": reason(d, operation)} for d in devices if d.id not in eligible]
        if not any(has_capability(d, operation.required_capability) for d in devices):
            continue
        response.append(
            OperationResponse(
                id=operation.id,
                label=operation.label,
                description=operation.description,
                category=operation.category,
                risk=operation.risk,
                confirmation=operation.confirmation,
                icon=operation.icon,
                eligible_device_ids=eligible,
                eligible_count=len(eligible),
                excluded_devices=excluded,
            )
        )
    return response


@router.post("/{operation_id}/jobs")
async def run_operation(
    operation_id: str,
    payload: OperationRunRequest,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    operation = OPERATION_BY_ID.get(operation_id)
    if not operation:
        raise HTTPException(status_code=404, detail="Operation not found")

    devices = db.query(Device).filter(Device.id.in_(payload.device_ids)).order_by(Device.hostname).all()
    if len(devices) != len(payload.device_ids):
        found = {device.id for device in devices}
        missing = [str(device_id) for device_id in payload.device_ids if device_id not in found]
        raise HTTPException(status_code=404, detail=f"Unknown device IDs: {', '.join(missing)}")

    unsupported = [f"{device.name}: {reason}" for device in devices if (reason := operation_ineligibility(device, operation))]
    if unsupported:
        raise HTTPException(status_code=409, detail="; ".join(unsupported))
    if operation.risk != "low":
        expected = ", ".join(device.name for device in devices)
        if payload.confirmation != expected:
            raise HTTPException(status_code=400, detail=f"Confirm the exact target names: {expected}")

    if operation.id in {"reachy.health", "reachy.logs.read"} and any(db.get(DeviceReservation, device.id) for device in devices):
        raise HTTPException(status_code=409, detail="A selected device has an active operation. Check Activity before inspecting it.")
    if operation.id == "reachy.recover":
        return await _recover_reachy(db, devices, user)
    if operation.id in {"reachy.health", "reachy.logs.read"}:
        return _start_reachy_inspection(db, devices, user, operation.id)
    if operation.id in {"reachy.daemon.restart", "reachy.software.update"}:
        return _start_reachy_remote_jobs(db, devices, user, operation.id, operation.label, payload.request_key)

    non_ssh = [
        device.name
        for device in devices
        if (device.transport or "ssh") != "ssh"
        and not (operation.id == REACHY_APP_RESET and device.ansible_user)
    ]
    if non_ssh:
        raise HTTPException(
            status_code=400,
            detail=f"{operation.label} requires an SSH-managed device: {', '.join(non_ssh)}",
        )

    extra_vars = None
    if operation.id == "system.update":
        extra_vars = {"fleet_approved_package_plans": _approved_package_plans(db, payload.preview_job_id, devices)}
    elif operation.id in {"services.inspect", "services.manage"}:
        if operation.id == "services.manage":
            if not payload.service_name or re.fullmatch(r"(ssh.*|sshd.*|systemd.*|dbus.*|NetworkManager.*|network.*|networking|docker.*|containerd.*|kubelet|k3s.*|rke2.*|snap.microk8s.*|crio.*|cri-o.*|fleet.*|firewalld|ufw)\.service", payload.service_name):
                raise HTTPException(status_code=400, detail="Select a non-critical installed .service unit")
        extra_vars = {"service_action": "status" if operation.id == "services.inspect" else payload.service_action, "service_name": payload.service_name or ""}
    elif operation.id in {"kubernetes.drain.execute", "kubernetes.resume"}:
        extra_vars = {"drain_action": "drain" if operation.id.endswith("execute") else "resume"}
    if operation.id == "nvidia.driver.manage":
        extra_vars = {"upgrade_mode": "standard"}
    elif operation.id == "firmware.update":
        extra_vars = {"firmware_mode": "update"}
    elif operation.id == "system.reboot":
        extra_vars = {"force_reboot": True}
    elif operation.id == "nvidia.fabric_manager.manage":
        extra_vars = {"fabric_action": "status"}
    elif operation.id == "nvidia.mig.manage":
        extra_vars = {"mig_action": "status"}
    elif operation.id == "kubernetes.drain":
        extra_vars = {"drain_action": "status"}

    job_id = await run_playbook(
        db=db,
        playbook=operation.playbook or "",
        hosts=[device.hostname for device in devices],
        extra_vars=extra_vars,
        triggered_by=user,
        request_key=payload.request_key,
    )
    return {
        "job_id": job_id,
        "detail": f"{operation.label} started on {len(devices)} device(s)",
    }


def _approved_package_plans(db, preview_job_id, devices):
    preview = db.query(Job).filter_by(job_id=preview_job_id).first() if preview_job_id else None
    targets = {device.hostname for device in devices}
    if not preview or preview.playbook != "package_preview.yml" or preview.status != "success" or set((preview.target_hosts or "").split(",")) != targets:
        raise HTTPException(status_code=409, detail="Run and review a successful package preview for these exact devices first")
    observed = preview.finished_at
    if observed and observed.tzinfo is None:
        observed = observed.replace(tzinfo=timezone.utc)
    if not observed or (datetime.now(timezone.utc) - observed).total_seconds() > 1800:
        raise HTTPException(status_code=409, detail="Package preview expired. Run a new preview (valid for 30 minutes)")
    plans = {r["hostname"]: r["fingerprint"] for r in get_job_results(preview.job_id) if r["report_type"] == "packages" and re.fullmatch(r"[a-f0-9]{64}", r.get("fingerprint", ""))}
    if set(plans) != targets:
        raise HTTPException(status_code=409, detail="Package preview is incomplete; run it again")
    return plans


def _apply_reachy_observation(device, result):
    device.status = "online" if result["reachable"] else "offline"
    device.facts_stale = not result["reachable"]
    if result["reachable"]:
        device.facts = result.get("facts", {})
        device.last_seen = datetime.now(timezone.utc)
        device.discovered_at = device.last_seen


async def _recover_reachy(db, devices, user):
    local = Job(job_id=str(uuid.uuid4()), playbook="reachy.recover", target_hosts=",".join(d.hostname for d in devices),
                status="running", phase="verifying", execution_kind="read_only", triggered_by=user, started_at=datetime.now(timezone.utc))
    try:
        reserve_devices(db, local, devices, recovery=True)
    except ExecutionConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    outcomes = []
    for device in devices:
        try:
            if device.recovery_required:
                previous = next((j for j in db.query(Job).filter(Job.execution_kind == "mutation").order_by(Job.created_at.desc()).all() if device.hostname in (j.target_hosts or "").split(",")), None)
                remote_id = next((item.get("remote_job_id") for item in previous.device_results if item.get("hostname") == device.hostname), None) if previous else None
                if not remote_id:
                    raise RuntimeError("No remote job ID was acknowledged. Inspect the daemon's operation history and repair through its maintenance interface; Fleet cannot certify completion automatically.")
                info = await asyncio.to_thread(reachy_request, device.endpoint or device.hostname, device.daemon_port or 8000, "/update/info", query={"job_id":remote_id}, timeout=10)
                if str(info.get("status", "")).lower() != "done":
                    raise RuntimeError("The recorded remote job has not completed successfully. Keep the device in recovery.")
            result = await asyncio.to_thread(probe_reachy, device.endpoint or device.hostname, device.daemon_port or 8000)
            _apply_reachy_observation(device, result)
            if not result["reachable"]:
                raise RuntimeError(result["detail"])
            device.recovery_required = False
            device.recovery_reason = None
            outcomes.append({"hostname":device.hostname, "status":"success"})
        except Exception as exc:
            outcomes.append({"hostname":device.hostname, "status":"failed", "detail":str(exc)})
    local.outcomes_json = json.dumps(outcomes)
    local.status = "success" if all(item["status"] == "success" for item in outcomes) else "failed"
    local.finished_at = datetime.now(timezone.utc)
    local.phase = "complete"
    local.output_log = json.dumps(outcomes, indent=2)
    local.error_summary = "; ".join(item.get("detail", "") for item in outcomes if item["status"] != "success") or None
    release_devices(db, local.job_id)
    db.commit()
    return {"job_id":local.job_id, "detail":"Reachy recovery verification completed"}


async def _collect_reachy_logs(endpoint, port):
    from websockets.asyncio.client import connect
    url = reachy_websocket_url(endpoint, port, "/logs/ws/daemon")
    lines = []
    async with connect(url, open_timeout=5, close_timeout=2, max_size=1_048_576) as socket:
        deadline = asyncio.get_running_loop().time() + 5
        while len(lines) < 100 and asyncio.get_running_loop().time() < deadline:
            try:
                async with asyncio.timeout(1.25):
                    message = await socket.recv()
            except TimeoutError:
                break
            if message:
                lines.append(str(message))
    return "\n".join(lines) or "No log lines received"


def _start_reachy_inspection(db, devices, user, operation_id="reachy.health"):
    job_id = str(uuid.uuid4())
    local = Job(job_id=job_id, playbook=operation_id, target_hosts=",".join(d.hostname for d in devices),
                status="pending", phase="queued", execution_kind="read_only", triggered_by=user)
    try:
        reserve_devices(db, local, devices)
    except ExecutionConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    targets = [(d.hostname, d.endpoint or d.hostname, d.daemon_port or 8000) for d in devices]

    async def execute():
        outcomes = []
        status = "failed"
        started = datetime.now(timezone.utc)
        error = None
        try:
            async with job_semaphore():
                _update_reachy_job(job_id, status="running", phase="inspecting", started_at=started)
                for hostname, endpoint, port in targets:
                    try:
                        if operation_id == "reachy.health":
                            result = await asyncio.to_thread(probe_reachy, endpoint, port)
                            with SessionLocal() as state_db:
                                device = state_db.query(Device).filter_by(hostname=hostname).one()
                                _apply_reachy_observation(device, result)
                                state_db.commit()
                            if not result["reachable"]:
                                raise RuntimeError(result["detail"])
                            output = json.dumps(result.get("facts", {}), indent=2)
                        else:
                            output = await _collect_reachy_logs(endpoint, port)
                        outcomes.append({"hostname":hostname, "status":"success"})
                        _append_reachy_log(job_id, f"[{hostname}]\n{output}\n")
                    except Exception as exc:
                        outcomes.append({"hostname":hostname, "status":"failed", "detail":str(exc)})
                        _append_reachy_log(job_id, f"[{hostname}] FAILED: {exc}\n")
                    _update_reachy_job(job_id, outcomes_json=json.dumps(outcomes))
                status = "success" if all(item["status"] == "success" for item in outcomes) else "failed"
                error = "; ".join(item.get("detail", "") for item in outcomes if item["status"] != "success") or None
        except asyncio.CancelledError:
            error = "Inspection interrupted by executor shutdown"
        finally:
            _update_reachy_job(job_id, status=status, phase="complete", finished_at=datetime.now(timezone.utc),
                duration_seconds=int((datetime.now(timezone.utc)-started).total_seconds()),
                error_summary=error, outcomes_json=json.dumps(outcomes), capture_log=True)

    track_task(execute())
    return {"job_id":job_id, "detail":f"Reachy inspection queued for {len(devices)} device(s)"}


def _start_reachy_remote_jobs(
    db: Session,
    devices: list[Device],
    user: str,
    operation_id: str,
    label: str,
    request_key: str | None = None,
) -> dict:
    fingerprint = request_fingerprint(operation_id, [d.hostname for d in devices], {})
    previous = db.query(Job).filter_by(request_key=request_key).first() if request_key else None
    if previous:
        if previous.request_fingerprint != fingerprint:
            raise HTTPException(status_code=409, detail="Request key already used for a different operation")
        return {"job_id":previous.job_id, "detail":"Operation already accepted"}
    job_id = str(uuid.uuid4())
    started = datetime.now(timezone.utc)
    job = Job(
        job_id=job_id,
        playbook=operation_id,
        target_hosts=",".join(device.hostname for device in devices),
        status="pending",
        started_at=started,
        triggered_by=user,
        output_log="",
        execution_kind="mutation", phase="queued", request_key=request_key, request_fingerprint=fingerprint,
    )
    try:
        reserve_devices(db, job, devices)
    except ExecutionConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    get_log_path(job_id).write_text(f"{label} queued for {len(devices)} Reachy device(s).\n")
    targets = [
        (device.hostname, device.name, device.endpoint or device.hostname, device.daemon_port or 8000)
        for device in devices
    ]
    track_task(_run_reachy_remote_jobs(job_id, targets, operation_id, label, started))
    return {"job_id": job_id, "detail": f"{label} started on {len(devices)} device(s)"}


async def _run_reachy_remote_jobs(job_id, targets, operation_id, label, started):
    async with job_semaphore():
        await _execute_reachy_remote_jobs(job_id, targets, operation_id, label, started)


async def _execute_reachy_remote_jobs(
    job_id: str,
    targets: list[tuple[str, str, str, int]],
    operation_id: str,
    label: str,
    started: datetime,
) -> None:
    outcomes = [{"hostname": hostname, "status": "not_started"} for hostname, _, _, _ in targets]
    _update_reachy_job(job_id, status="running", phase="executing", outcomes_json=json.dumps(outcomes))
    failures = []
    try:
        for index, (hostname, name, endpoint, port) in enumerate(targets):
            _append_reachy_log(job_id, f"\n[{name}] Starting {label.lower()}…\n")
            start_path = "/api/daemon/restart" if operation_id == "reachy.daemon.restart" else "/update/start"
            outcome = outcomes[index]
            outcome["status"] = "running"
            _update_reachy_job(job_id, outcomes_json=json.dumps(outcomes))
            try:
                response = await asyncio.to_thread(reachy_request, endpoint, port, start_path, method="POST", timeout=15)
                remote_job_id = str(response.get("job_id") or "")
                if not remote_job_id:
                    raise RuntimeError("Reachy daemon did not return a job ID; remote state is uncertain")
                outcome["remote_job_id"] = remote_job_id
                _update_reachy_job(job_id, outcomes_json=json.dumps(outcomes))
                await _poll_reachy_job(job_id, name, endpoint, port, remote_job_id)
                result = await asyncio.to_thread(probe_reachy, endpoint, port)
                if not result["reachable"]:
                    raise RuntimeError("Remote job completed but daemon health could not be verified")
                with SessionLocal() as db:
                    device = db.query(Device).filter_by(hostname=hostname).one()
                    _apply_reachy_observation(device, result)
                    db.commit()
                outcome["status"] = "success"
            except Exception as exc:
                outcome["status"] = "recovery_required"
                failures.append(f"{name}: {exc}")
                _append_reachy_log(job_id, f"[{name}] FAILED: {exc}\n")
            _update_reachy_job(job_id, outcomes_json=json.dumps(outcomes))
    except asyncio.CancelledError:
        failures.append("Executor stopped while tracking the remote job. Verify recovery; do not repeat the change.")
        for outcome in outcomes:
            if outcome["status"] == "running":
                outcome["status"] = "recovery_required"
    finally:
        finished = datetime.now(timezone.utc)
        succeeded = not failures
        _update_reachy_job(job_id, status="success" if succeeded else "recovery_required", phase="complete",
            finished_at=finished, duration_seconds=max(0, int((finished - started).total_seconds())),
            error_summary="\n".join(failures) or None, outcomes_json=json.dumps(outcomes),
            recap=f"{label}: {sum(item['status'] == 'success' for item in outcomes)}/{len(targets)} completed", capture_log=True)


async def _poll_reachy_job(
    local_job_id: str,
    name: str,
    endpoint: str,
    port: int,
    remote_job_id: str,
) -> None:
    emitted = 0
    deadline = time.monotonic() + 1800
    last_error = ""
    while time.monotonic() < deadline:
        try:
            info = await asyncio.to_thread(reachy_request, endpoint, port, "/update/info",
                query={"job_id":remote_job_id}, timeout=max(.1, min(10, deadline - time.monotonic())))
        except RuntimeError as exc:
            message = str(exc)
            if re.search(r"HTTP 4(?!04)\d\d", message):
                raise
            if message != last_error:
                _append_reachy_log(local_job_id, f"[{name}] Waiting for daemon connectivity: {message}\n")
            last_error = message
            await asyncio.sleep(min(2, max(0, deadline - time.monotonic())))
            continue
        logs = info.get("logs") if isinstance(info.get("logs"), list) else []
        for line in logs[emitted:]:
            _append_reachy_log(local_job_id, f"[{name}] {line}\n")
        emitted = len(logs)
        status = str(info.get("status") or "").lower()
        if status == "done":
            _append_reachy_log(local_job_id, f"[{name}] Completed successfully.\n")
            return
        if status == "failed":
            raise RuntimeError("Reachy daemon reported that the job failed")
        await asyncio.sleep(min(2, max(0, deadline - time.monotonic())))
    raise RuntimeError(f"Reachy daemon job exceeded its 30-minute deadline. {last_error}")


def _append_reachy_log(job_id: str, text: str) -> None:
    with get_log_path(job_id).open("a") as handle:
        handle.write(text)


def _update_reachy_job(job_id: str, capture_log: bool = False, **values) -> None:
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.job_id == job_id).first()
        if not job:
            return
        for key, value in values.items():
            setattr(job, key, value)
        if capture_log:
            log_path = get_log_path(job_id)
            job.output_log = log_path.read_text() if log_path.exists() else ""
        if job.status == "running" and job.execution_kind == "mutation":
            for device in db.query(Device).filter(Device.hostname.in_((job.target_hosts or "").split(","))).all():
                if not any(item.get("hostname") == device.hostname and item.get("status") == "success" for item in job.device_results):
                    device.facts_stale = True
        if job.status in {"success", "failed", "recovery_required", "cancelled"}:
            release_devices(db, job_id)
            for device in db.query(Device).filter(Device.hostname.in_((job.target_hosts or "").split(","))).all():
                outcome = next((item for item in job.device_results if item.get("hostname") == device.hostname), {})
                if outcome.get("status") == "success":
                    continue
                if job.playbook != "reachy.logs.read":
                    device.facts_stale = True
                if outcome.get("status") != "not_started" and job.status == "recovery_required":
                    device.recovery_required = True
                    device.recovery_reason = f"Remote job {job_id} requires health verification"
        db.commit()
    finally:
        db.close()
