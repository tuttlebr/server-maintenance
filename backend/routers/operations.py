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
from backend.capabilities import OPERATION_BY_ID, OPERATIONS, REACHY_DAEMON_RESTART, operation_ineligibility
from backend.database import SessionLocal, get_db
from backend.models import Device, Job, DeviceReservation
from backend.schemas import OperationResponse, OperationRunRequest
from backend.services.ansible_runner import get_log_path, run_playbook, track_task, job_semaphore
from backend.services.job_results import get_job_results
from backend.services.execution_state import TERMINAL_STATUSES, ExecutionConflict, completed_status, reserve_devices, release_devices, request_fingerprint
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

    if payload.request_key:
        previous = db.query(Job).filter_by(request_key=payload.request_key).first()
        if previous:
            previous_vars = json.loads(previous.extra_vars or "{}")
            same_preview = operation.id != "system.update" or _preview_matches_accepted(db, payload.preview_job_id, previous_vars)
            if (previous.playbook != (operation.playbook or operation.id) or
                    set((previous.target_hosts or "").split(",")) != {d.hostname for d in devices} or
                    previous.triggered_by != user or not same_preview):
                raise HTTPException(status_code=409, detail="Request key already used for a different operation")
            return {"job_id": previous.job_id, "detail": "Operation already accepted"}

    unsupported = [f"{device.name}: {reason}" for device in devices if (reason := operation_ineligibility(device, operation))]
    if unsupported:
        raise HTTPException(status_code=409, detail="; ".join(unsupported))
    if operation.risk != "low":
        expected = ", ".join(device.name for device in devices)
        if payload.confirmation != expected:
            raise HTTPException(status_code=400, detail=f"Confirm the exact target names: {expected}")

    if operation.id == REACHY_DAEMON_RESTART:
        return _start_reachy_remote_jobs(db, devices, user, operation.id, operation.label, payload.request_key)

    extra_vars = None
    if operation.id == "system.update":
        extra_vars = {"fleet_approved_package_plans": _approved_package_plans(db, payload.preview_job_id, devices)}

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


def _preview_matches_accepted(db, preview_job_id, values):
    preview = db.query(Job).filter_by(job_id=preview_job_id, playbook="package_preview.yml").first() if preview_job_id else None
    plans = {r["hostname"]: r.get("fingerprint") for r in get_job_results(preview.job_id) if r["report_type"] == "packages"} if preview else {}
    return bool(plans) and plans == values.get("fleet_approved_package_plans")


def _approved_package_plans(db, preview_job_id, devices):
    preview = db.query(Job).filter_by(job_id=preview_job_id).first() if preview_job_id else None
    targets = {device.hostname for device in devices}
    if not preview or preview.playbook != "package_preview.yml" or preview.status != "success" or set((preview.target_hosts or "").split(",")) != targets:
        raise HTTPException(status_code=409, detail="Check for apt updates on these exact devices first")
    observed = preview.finished_at
    if observed and observed.tzinfo is None:
        observed = observed.replace(tzinfo=timezone.utc)
    if not observed or (datetime.now(timezone.utc) - observed).total_seconds() > 1800:
        raise HTTPException(status_code=409, detail="The package check expired. Check for updates again (valid for 30 minutes)")
    plans = {r["hostname"]: r["fingerprint"] for r in get_job_results(preview.job_id) if r["report_type"] == "packages" and re.fullmatch(r"[a-f0-9]{64}", r.get("fingerprint", ""))}
    if set(plans) != targets:
        raise HTTPException(status_code=409, detail="The package check is incomplete. Check for updates again")
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
            previous = None
            if device.recovery_required:
                previous = next((j for j in db.query(Job).filter(Job.execution_kind == "mutation").order_by(Job.created_at.desc()).all() if device.hostname in (j.target_hosts or "").split(",")), None)
                remote_id = next((item.get("remote_job_id") for item in previous.device_results if item.get("hostname") == device.hostname), None) if previous else None
                if not remote_id:
                    raise RuntimeError("No remote job ID was acknowledged. Inspect the daemon's operation history and repair through its maintenance interface; Fleet cannot certify completion automatically.")
                info = await asyncio.to_thread(reachy_request, device.endpoint or device.hostname, device.daemon_port or 8000, "/update/info", query={"job_id":remote_id}, timeout=10)
                if str(info.get("status", "")).lower() != "done":
                    raise RuntimeError("The recorded remote job has not completed successfully. Keep the device in recovery.")
            if previous and previous.playbook == REACHY_DAEMON_RESTART:
                result = await _wait_for_reachy_health(local.job_id, device.name, device.endpoint or device.hostname, device.daemon_port or 8000)
            else:
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
    local.status = completed_status(outcomes)
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
                status = completed_status(outcomes)
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
        with SessionLocal() as db:
            job = db.query(Job).filter_by(job_id=job_id).first()
            if not job or job.status != "pending":
                return
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
            start_path = "/api/daemon/restart" if operation_id == REACHY_DAEMON_RESTART else "/update/start"
            outcome = outcomes[index]
            outcome["status"] = "running"
            _update_reachy_job(job_id, phase="executing", outcomes_json=json.dumps(outcomes))
            try:
                response = await asyncio.to_thread(reachy_request, endpoint, port, start_path, method="POST", timeout=15)
                remote_job_id = str(response.get("job_id") or "")
                if not remote_job_id:
                    raise RuntimeError("Reachy daemon did not return a job ID; remote state is uncertain")
                outcome["remote_job_id"] = remote_job_id
                _update_reachy_job(job_id, outcomes_json=json.dumps(outcomes))
                await _poll_reachy_job(job_id, name, endpoint, port, remote_job_id)
                _update_reachy_job(job_id, phase="verifying")
                result = (await _wait_for_reachy_health(job_id, name, endpoint, port)
                          if operation_id == REACHY_DAEMON_RESTART
                          else await asyncio.to_thread(probe_reachy, endpoint, port))
                if not result["reachable"]:
                    raise RuntimeError("Remote job completed but daemon health could not be verified")
                with SessionLocal() as db:
                    device = db.query(Device).filter_by(hostname=hostname).one()
                    _apply_reachy_observation(device, result)
                    db.commit()
                outcome["status"] = "success"
            except Exception as exc:
                rejected = not outcome.get("remote_job_id") and re.search(r"Reachy daemon returned HTTP 4\d\d:", str(exc))
                outcome["status"] = "failed" if rejected else "recovery_required"
                outcome["detail"] = str(exc)
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
        status = "recovery_required" if any(item["status"] == "recovery_required" for item in outcomes) else completed_status(outcomes, has_errors=bool(failures))
        _update_reachy_job(job_id, status=status, phase="complete",
            finished_at=finished, duration_seconds=max(0, int((finished - started).total_seconds())),
            error_summary="\n".join(failures) or None, outcomes_json=json.dumps(outcomes),
            recap=f"{label}: {sum(item['status'] == 'success' for item in outcomes)}/{len(targets)} completed", capture_log=True)


async def _wait_for_reachy_health(job_id, name, endpoint, port):
    deadline = time.monotonic() + 90
    detail = "No healthy daemon response"
    _append_reachy_log(job_id, f"[{name}] Waiting for daemon and robot backend readiness.\n")
    while time.monotonic() < deadline:
        result = await asyncio.to_thread(probe_reachy, endpoint, port)
        daemon = result.get("facts", {}).get("daemon") or {}
        backend = daemon.get("backend_status") or {}
        if (result["reachable"] and daemon.get("state") == "running" and
                backend.get("ready") is True and not daemon.get("error") and not backend.get("error")):
            _append_reachy_log(job_id, f"[{name}] Daemon running; robot backend ready.\n")
            return result
        detail = (daemon.get("error") or backend.get("error") or
                  (f"Daemon state: {daemon.get('state', 'unknown')}; backend ready: {backend.get('ready', 'unknown')}"
                   if result["reachable"] else result.get("detail", "Daemon unreachable")))
        await asyncio.sleep(min(2, max(0, deadline - time.monotonic())))
    raise RuntimeError(f"Restart finished but daemon health could not be verified: {detail}")


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
        if job.status in TERMINAL_STATUSES:
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
