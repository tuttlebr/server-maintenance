from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.auth import get_current_user
from backend.capabilities import OPERATION_BY_ID, OPERATIONS, has_capability
from backend.database import SessionLocal, get_db
from backend.models import Device, Job
from backend.schemas import OperationResponse, OperationRunRequest
from backend.services.ansible_runner import get_log_path, run_playbook
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
    for operation in OPERATIONS:
        eligible = [device.id for device in devices if has_capability(device, operation.required_capability)]
        if not eligible:
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

    unsupported = [device.name for device in devices if not has_capability(device, operation.required_capability)]
    if unsupported:
        raise HTTPException(
            status_code=400,
            detail=f"{operation.label} is not supported on: {', '.join(unsupported)}",
        )

    if operation.id == "reachy.health":
        return _run_reachy_health(db, devices, user)
    if operation.id == "reachy.logs.read":
        return await _run_reachy_logs(db, devices, user)
    if operation.id in {"reachy.daemon.restart", "reachy.software.update"}:
        return _start_reachy_remote_jobs(db, devices, user, operation.id, operation.label)

    non_ssh = [device.name for device in devices if (device.transport or "ssh") != "ssh"]
    if non_ssh:
        raise HTTPException(
            status_code=400,
            detail=f"{operation.label} requires an SSH-managed device: {', '.join(non_ssh)}",
        )

    extra_vars = None
    if operation.id == "nvidia.driver.manage":
        extra_vars = {"upgrade_mode": "standard"}
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
    )
    return {
        "job_id": job_id,
        "detail": f"{operation.label} started on {len(devices)} device(s)",
    }


def _run_reachy_health(db: Session, devices: list[Device], user: str) -> dict:
    started = datetime.now(timezone.utc)
    results = []
    for device in devices:
        result = probe_reachy(device.endpoint or device.hostname, device.daemon_port or 8000)
        device.status = "online" if result["reachable"] else "offline"
        if result["reachable"]:
            device.last_seen = datetime.now(timezone.utc)
            device.facts = result.get("facts", {})
        results.append({"device": device.name, "reachable": result["reachable"], "detail": result["detail"]})

    finished = datetime.now(timezone.utc)
    succeeded = all(result["reachable"] for result in results)
    job_id = str(uuid.uuid4())
    job = Job(
        job_id=job_id,
        playbook="reachy.health",
        target_hosts=",".join(device.hostname for device in devices),
        status="success" if succeeded else "failed",
        started_at=started,
        finished_at=finished,
        duration_seconds=max(0, int((finished - started).total_seconds())),
        triggered_by=user,
        output_log=json.dumps(results, indent=2),
        error_summary=None if succeeded else "One or more Reachy daemons did not respond",
        recap=f"Reachy health: {sum(result['reachable'] for result in results)}/{len(results)} reachable",
    )
    db.add(job)
    db.commit()
    return {"job_id": job_id, "detail": job.recap}


async def _run_reachy_logs(db: Session, devices: list[Device], user: str) -> dict:
    """Collect a bounded snapshot from the daemon's documented log stream."""
    started = datetime.now(timezone.utc)
    output = []
    failures = []
    from websockets.asyncio.client import connect

    for device in devices:
        url = reachy_websocket_url(
            device.endpoint or device.hostname,
            device.daemon_port or 8000,
            "/logs/ws/daemon",
        )
        lines = []
        try:
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
        except Exception as exc:
            failures.append(f"{device.name}: {exc}")
        output.append(f"## {device.name}\n" + ("\n".join(lines) if lines else "No log lines received"))

    finished = datetime.now(timezone.utc)
    job_id = str(uuid.uuid4())
    succeeded = not failures
    job = Job(
        job_id=job_id,
        playbook="reachy.logs.read",
        target_hosts=",".join(device.hostname for device in devices),
        status="success" if succeeded else "failed",
        started_at=started,
        finished_at=finished,
        duration_seconds=max(0, int((finished - started).total_seconds())),
        triggered_by=user,
        output_log="\n\n".join(output),
        error_summary="\n".join(failures) if failures else None,
        recap=f"Reachy logs: {len(devices) - len(failures)}/{len(devices)} collected",
    )
    db.add(job)
    db.commit()
    return {"job_id": job_id, "detail": job.recap}


def _start_reachy_remote_jobs(
    db: Session,
    devices: list[Device],
    user: str,
    operation_id: str,
    label: str,
) -> dict:
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
    )
    db.add(job)
    db.commit()
    get_log_path(job_id).write_text(f"{label} queued for {len(devices)} Reachy device(s).\n")
    targets = [
        (device.name, device.endpoint or device.hostname, device.daemon_port or 8000)
        for device in devices
    ]
    asyncio.create_task(_run_reachy_remote_jobs(job_id, targets, operation_id, label, started))
    return {"job_id": job_id, "detail": f"{label} started on {len(devices)} device(s)"}


async def _run_reachy_remote_jobs(
    job_id: str,
    targets: list[tuple[str, str, int]],
    operation_id: str,
    label: str,
    started: datetime,
) -> None:
    _update_reachy_job(job_id, status="running")
    failures = []
    for name, endpoint, port in targets:
        _append_reachy_log(job_id, f"\n[{name}] Starting {label.lower()}…\n")
        start_path = "/api/daemon/restart" if operation_id == "reachy.daemon.restart" else "/update/start"
        try:
            response = await asyncio.to_thread(
                reachy_request,
                endpoint,
                port,
                start_path,
                method="POST",
                timeout=15,
            )
            remote_job_id = str(response.get("job_id") or "")
            if not remote_job_id:
                raise RuntimeError("Reachy daemon did not return a job ID")
            await _poll_reachy_job(job_id, name, endpoint, port, remote_job_id)
        except Exception as exc:
            failures.append(f"{name}: {exc}")
            _append_reachy_log(job_id, f"[{name}] FAILED: {exc}\n")

    finished = datetime.now(timezone.utc)
    succeeded = not failures
    _update_reachy_job(
        job_id,
        status="success" if succeeded else "failed",
        finished_at=finished,
        duration_seconds=max(0, int((finished - started).total_seconds())),
        error_summary="\n".join(failures) if failures else None,
        recap=f"{label}: {len(targets) - len(failures)}/{len(targets)} completed",
        capture_log=True,
    )


async def _poll_reachy_job(
    local_job_id: str,
    name: str,
    endpoint: str,
    port: int,
    remote_job_id: str,
) -> None:
    emitted = 0
    for _ in range(900):
        info = await asyncio.to_thread(
            reachy_request,
            endpoint,
            port,
            "/update/info",
            query={"job_id": remote_job_id},
            timeout=10,
        )
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
        await asyncio.sleep(2)
    raise RuntimeError("Reachy daemon job timed out after 30 minutes")


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
        db.commit()
    finally:
        db.close()
