"""Durable reservations and explicit recovery; never replay a mutation after restart."""
import fcntl
import hashlib
import hmac
import json
import re
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError

from backend.config import settings
from backend.models import Device, DeviceReservation, Job, UserHostAssociation

ACTIVE_STATUSES = {"pending", "running", "cancelling"}
TERMINAL_STATUSES = {"success", "failed", "cancelled", "recovery_required"}
READ_ONLY_PLAYBOOKS = {
    "host_facts.yml", "maintenance_assessment.yml", "preflight_check.yml",
    "health_diagnostics.yml", "storage_analysis.yml", "gpu_usage.yml",
    "firmware_inventory.yml", "package_preview.yml", "access_inspect.yml",
    "recovery_check.yml",
}


class ExecutionConflict(ValueError):
    pass


def acquire_executor_lock():
    """This deployment runs one executor. Refuse competing web workers explicitly."""
    path = settings.data_dir / "executor.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        raise RuntimeError("Another Fleet executor owns this data directory. Run one web worker.")
    return handle


def is_read_only(playbook, extra_vars=None):
    values = extra_vars or {}
    if playbook in READ_ONLY_PLAYBOOKS or playbook in {"reachy.health", "reachy.logs.read"}:
        return True
    return any((playbook == name and values.get(key, "status") == "status") for name, key in (
        ("fabric_manager.yml", "fabric_action"), ("mig_management.yml", "mig_action"),
        ("host_drain.yml", "drain_action"), ("service_control.yml", "service_action"),
    ))


def request_fingerprint(playbook, targets, values):
    return hmac.new(settings.secret_key.encode(), json.dumps([playbook, sorted(targets), values or {}], sort_keys=True).encode(), hashlib.sha256).hexdigest()


def reserve_devices(db, job, devices, *, recovery=False):
    for device in devices:
        if device.recovery_required and job.execution_kind != "read_only" and not recovery:
            raise ExecutionConflict(f"{device.name} requires recovery verification before another change")
        existing = db.get(DeviceReservation, device.id)
        if existing:
            raise ExecutionConflict(f"{device.name} is reserved by job {existing.job_id}")
    try:
        db.add(job)
        db.flush()
        for device in devices:
            db.add(DeviceReservation(device_id=device.id, job_id=job.job_id))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ExecutionConflict("A selected device was reserved by another request; refresh activity") from exc


def release_devices(db, job_id):
    db.query(DeviceReservation).filter_by(job_id=job_id).delete(synchronize_session=False)


def reconcile_interrupted_jobs(db):
    now = datetime.now(timezone.utc)
    for job in db.query(Job).filter(Job.status.in_(ACTIVE_STATUSES)).all():
        started = job.status != "pending"
        recovery = started and job.execution_kind != "read_only"
        job.status = "recovery_required" if recovery else ("failed" if started else "cancelled")
        job.phase = "interrupted"
        job.finished_at = now
        log_path = settings.data_dir / "logs" / f"{job.job_id}.log"
        if log_path.is_file():
            job.output_log = log_path.read_text()
        job.error_summary = (
            "Executor stopped during this operation. Remote state is uncertain; inspect and verify recovery."
            if started else "Executor stopped before this queued job began. No automatic replay was attempted."
        )
        targets = (job.target_hosts or "").split(",")
        previous = {item["hostname"]: item for item in job.device_results if "hostname" in item}
        job.outcomes_json = json.dumps([{**previous.get(name, {}), "hostname": name, "status": job.status} for name in targets if name])
        if started:
            for device in db.query(Device).filter(Device.hostname.in_(targets)).all():
                device.facts_stale = True
                for association in db.query(UserHostAssociation).filter_by(host_id=device.id).all():
                    association.state = "unverified"
                if recovery:
                    device.recovery_required = True
                    device.recovery_reason = f"Interrupted job {job.job_id} ({job.playbook})"
    db.query(DeviceReservation).delete(synchronize_session=False)
    db.commit()


def parse_host_outcomes(output, targets):
    """Only a complete, successful host recap proves execution on that host."""
    recaps = {}
    for line in output.splitlines():
        match = re.match(r"^(\S+)\s*:\s+ok=(\d+)\s+changed=(\d+)\s+unreachable=(\d+)\s+failed=(\d+)", line)
        if match:
            name, ok, changed, unreachable, failed = match.groups()
            values = dict(ok=int(ok), changed=int(changed), unreachable=int(unreachable), failed=int(failed))
            status = "unreachable" if values["unreachable"] else "failed" if values["failed"] else "success" if values["ok"] else "not_checked"
            recaps[name] = {"hostname": name, "status": status, **values}
    return [recaps.get(name, {"hostname": name, "status": "not_checked"}) for name in targets]
