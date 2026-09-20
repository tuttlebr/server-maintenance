import asyncio
import errno
import sys
import time
import json
import logging
import os
import re
import subprocess
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from backend.config import settings
from backend.database import SessionLocal
from backend.models import Host, Job, ManagedUser, UserHostAssociation
from backend.services.execution_state import (ExecutionConflict, is_read_only, parse_host_outcomes, request_fingerprint, reserve_devices, release_devices)
from backend.services.job_results import get_job_results
from backend.services import job_log_indexer
from backend.capabilities import NVIDIA_FABRIC_MANAGER, REACHY_APP_RESET, has_capability
from backend.services.device_discovery import enrich_from_scan
from backend.services.inventory_writer import regenerate_inventory
from backend.services.secret_store import decrypt_secret

logger = logging.getLogger(__name__)

SENSITIVE_KEYS = {"password", "new_password", "temp_password", "default_password"}
SENSITIVE_KEY_PARTS = ("password", "secret", "token", "api_key")
JINJA_MARKERS = ("{{", "}}", "{%", "%}", "{#", "#}")
FLEET_CREDENTIALS_VAR = "__fleet_host_credentials"
FLEET_JOB_ID_VAR = "__fleet_job_id"
FLEET_RESULTS_DIR_VAR = "__fleet_results_dir"
FLEET_SCAN_DIR_VAR = "__fleet_scan_dir"
RESERVED_EXTRA_VARS = {
    FLEET_CREDENTIALS_VAR,
    FLEET_JOB_ID_VAR,
    FLEET_RESULTS_DIR_VAR,
    FLEET_SCAN_DIR_VAR,
    "ansible_password",
    "ansible_ssh_pass",
    "ansible_become_password",
    "ansible_become_pass",
}
ALLOWED_PLAYBOOKS = {
    "package_preview.yml", "service_control.yml", "recovery_check.yml", "access_inspect.yml",
    "admin_setup.yml",
    "bulk_password_reset.yml",
    "change_password.yml",
    "docker_cleanup.yml",
    "driver_upgrade.yml",
    "fabric_manager.yml",
    "firmware_inventory.yml",
    "firmware_update.yml",
    "gpu_usage.yml",
    "health_diagnostics.yml",
    "host_bootstrap.yml",
    "host_drain.yml",
    "host_facts.yml",
    "install_docker.yml",
    "manage_groups.yml",
    "manage_sudoers.yml",
    "maintenance_assessment.yml",
    "mig_management.yml",
    "preflight_check.yml",
    "reboot.yml",
    "reachy_app_reset.yml",
    "remove_sudoers.yml",
    "remove_user.yml",
    "storage_analysis.yml",
    "system_update.yml",
    "user_management.yml",
}

_PROCESS_LOCK = threading.Lock()
_RUNNING_PROCS: dict[str, subprocess.Popen] = {}
_CANCELLED_JOBS: set[str] = set()
_JOB_SEMAPHORE: asyncio.Semaphore | None = None
_BACKGROUND_TASKS: set[asyncio.Task] = set()
_EXECUTOR_LEASE = None


def set_executor_lease(handle):
    global _EXECUTOR_LEASE
    _EXECUTOR_LEASE = handle


async def _execute(*args):
    work = asyncio.create_task(asyncio.to_thread(_run_playbook_streaming, *args))
    try:
        return await asyncio.shield(work)
    except asyncio.CancelledError:
        cancel_job(args[4])
        await asyncio.shield(work)
        raise


def track_task(coroutine):
    task = asyncio.create_task(coroutine)
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)
    return task


async def shutdown_executor():
    with _PROCESS_LOCK:
        for proc in _RUNNING_PROCS.values():
            proc.terminate()
    for task in list(_BACKGROUND_TASKS):
        task.cancel()
    if _BACKGROUND_TASKS:
        await asyncio.gather(*list(_BACKGROUND_TASKS), return_exceptions=True)


class PlaybookRequestError(ValueError):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def redact_extra_vars(extra_vars: dict) -> str:
    return json.dumps(_redact_value(extra_vars))


def _redact_value(value):
    if isinstance(value, dict):
        redacted = {}
        for key, nested in value.items():
            key_lower = str(key).lower()
            if key_lower in SENSITIVE_KEYS or any(part in key_lower for part in SENSITIVE_KEY_PARTS):
                redacted[key] = "***REDACTED***"
            else:
                redacted[key] = _redact_value(nested)
        return redacted
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    return value


def _validate_extra_vars(value, path: str = "extra_vars") -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if path == "extra_vars" and str(key) in RESERVED_EXTRA_VARS:
                raise PlaybookRequestError(f"{path}.{key} is reserved for fleet connection credentials")
            _validate_extra_vars(str(key), f"{path}.key")
            _validate_extra_vars(nested, f"{path}.{key}")
        return
    if isinstance(value, list):
        for index, nested in enumerate(value):
            _validate_extra_vars(nested, f"{path}[{index}]")
        return
    if not isinstance(value, str):
        return
    if "\x00" in value or "\r" in value or "\n" in value:
        raise PlaybookRequestError(f"{path} contains unsupported control characters")
    if any(marker in value for marker in JINJA_MARKERS):
        raise PlaybookRequestError(f"{path} must not contain Ansible template expressions")


def _sensitive_values(value, key_name: str = "") -> set[str]:
    values = set()
    if isinstance(value, dict):
        for key, nested in value.items():
            values.update(_sensitive_values(nested, str(key)))
    elif isinstance(value, list):
        for nested in value:
            values.update(_sensitive_values(nested, key_name))
    elif isinstance(value, str) and (
        key_name.lower() in SENSITIVE_KEYS
        or any(part in key_name.lower() for part in SENSITIVE_KEY_PARTS)
    ):
        values.add(value)
    return values


def _redact_output_line(line: str, secrets: set[str]) -> str:
    for secret in sorted((value for value in secrets if value), key=len, reverse=True):
        line = line.replace(secret, "***REDACTED***")
    return line


def _extract_recap(output: str) -> str | None:
    """Extract the PLAY RECAP block from Ansible output."""
    if not output:
        return None
    lines = output.splitlines()
    recap_lines = []
    in_recap = False
    for line in lines:
        if "PLAY RECAP" in line:
            in_recap = True
            recap_lines.append(line)
            continue
        if in_recap:
            stripped = line.strip()
            if stripped == "":
                break
            recap_lines.append(line)
    return "\n".join(recap_lines) if recap_lines else None


def _extract_unreachable_hosts(output: str) -> set[str]:
    """Extract hosts with unreachable > 0 from the Ansible PLAY RECAP."""
    unreachable = set()
    if not output:
        return unreachable
    in_recap = False
    for line in output.splitlines():
        if "PLAY RECAP" in line:
            in_recap = True
            continue
        if not in_recap:
            continue
        if not line.strip():
            break
        host_match = re.match(r"^(\S+)\s*:", line)
        unreachable_match = re.search(r"\bunreachable=(\d+)", line)
        if host_match and unreachable_match and int(unreachable_match.group(1)) > 0:
            unreachable.add(host_match.group(1))
    return unreachable


def get_log_path(job_id: str) -> Path:
    """Return the path to a job's streaming log file."""
    log_dir = settings.data_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / f"{job_id}.log"


def _run_playbook_streaming(
    playbook: str,
    targets: list[str],
    extra_vars: dict | None,
    host_credentials: dict[str, dict[str, str]],
    job_id: str,
    timeout_seconds: int,
    append: bool = False,
) -> int:
    """Run ansible-playbook, streaming output to a log file line by line. Returns rc."""
    ansible_dir = settings.ansible_dir
    log_path = get_log_path(job_id)

    env_vars = {
        "ANSIBLE_CONFIG": str(ansible_dir / "ansible.cfg"),
        "ANSIBLE_INVENTORY": str(settings.resolved_inventory_file),
        "ANSIBLE_HOST_KEY_CHECKING": "True",
        "ANSIBLE_FORCE_COLOR": "0",
        "ANSIBLE_NOCOLOR": "1",
        "ANSIBLE_FORKS": str(settings.ansible_forks),
        "PYTHONUNBUFFERED": "1",
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "HOME": str(Path.home()),
    }
    if os.environ.get("SSH_AUTH_SOCK"):
        env_vars["SSH_AUTH_SOCK"] = os.environ["SSH_AUTH_SOCK"]
    if os.environ.get("KUBECONFIG"):
        env_vars["KUBECONFIG"] = os.environ["KUBECONFIG"]

    log_fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | (os.O_APPEND if append else os.O_TRUNC), 0o600)
    with os.fdopen(log_fd, "a" if append else "w") as log_file:
        if append:
            log_file.write("\n--- Post-operation facts ---\n")
            log_file.flush()
        payload = dict(extra_vars or {})
        payload[FLEET_JOB_ID_VAR] = job_id
        payload[FLEET_RESULTS_DIR_VAR] = str(settings.data_dir / "job-results")
        payload[FLEET_SCAN_DIR_VAR] = str(settings.data_dir / "scans" / job_id)
        credentials = {
            target: host_credentials[target]
            for target in targets
            if host_credentials.get(target)
        }
        if credentials:
            payload[FLEET_CREDENTIALS_VAR] = credentials
            if any("ansible_password" in values for values in credentials.values()):
                payload["ansible_password"] = (
                    "{{ "
                    + FLEET_CREDENTIALS_VAR
                    + ".get(inventory_hostname, {}).get('ansible_password', '') }}"
                )
            if any("ansible_become_password" in values for values in credentials.values()):
                payload["ansible_become_password"] = (
                    "{{ "
                    + FLEET_CREDENTIALS_VAR
                    + ".get(inventory_hostname, {}).get('ansible_become_password', '') }}"
                )

        secrets = _sensitive_values(payload)
        cmd = [
            "ansible-playbook",
            str(ansible_dir / "playbooks" / playbook),
            "-v",
            "--limit",
            ",".join(targets),
        ]
        # The supervisor kills the entire Ansible/SSH group if this process exits.
        parent_read, parent_write = os.pipe()
        proc = None
        reader = None
        deadline = time.monotonic() + timeout_seconds
        try:
            with tempfile.TemporaryDirectory(prefix="fleet-extra-vars-") as secret_dir:
                extra_vars_path = Path(secret_dir) / "payload.json"
                os.mkfifo(extra_vars_path, 0o600)
                cmd.extend(["--extra-vars", f"@{extra_vars_path}"])
                supervisor = Path(__file__).with_name("process_supervisor.py")
                proc = subprocess.Popen(
                    [sys.executable, str(supervisor), str(parent_read), *cmd],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                    bufsize=1, env=env_vars, cwd=str(ansible_dir), pass_fds=(parent_read,) + ((_EXECUTOR_LEASE.fileno(),) if _EXECUTOR_LEASE else ()),
                )
                os.close(parent_read)
                parent_read = None
                with _PROCESS_LOCK:
                    _RUNNING_PROCS[job_id] = proc
                    if job_id in _CANCELLED_JOBS:
                        proc.terminate()

                def _copy_output():
                    for line in proc.stdout:
                        log_file.write(_redact_output_line(line, secrets))
                        log_file.flush()

                reader = threading.Thread(target=_copy_output, daemon=True)
                reader.start()
                # Never block indefinitely opening a FIFO when Ansible exits early.
                pipe_fd = None
                try:
                    handshake_deadline = min(deadline, time.monotonic() + 30)
                    while proc.poll() is None and time.monotonic() < handshake_deadline:
                        try:
                            pipe_fd = os.open(extra_vars_path, os.O_WRONLY | os.O_NONBLOCK)
                            break
                        except OSError as exc:
                            if exc.errno != errno.ENXIO:
                                raise
                            time.sleep(0.02)
                    if pipe_fd is None and proc.poll() is None:
                        raise subprocess.TimeoutExpired(cmd, timeout_seconds)
                    if pipe_fd is not None:
                        remaining = memoryview(json.dumps(payload, allow_nan=False).encode())
                        while remaining and proc.poll() is None:
                            if time.monotonic() >= deadline:
                                raise subprocess.TimeoutExpired(cmd, timeout_seconds)
                            try:
                                remaining = remaining[os.write(pipe_fd, remaining):]
                            except BlockingIOError:
                                time.sleep(0.02)
                            except BrokenPipeError:
                                break
                finally:
                    if pipe_fd is not None:
                        os.close(pipe_fd)
                proc.wait(timeout=max(0.01, deadline - time.monotonic()))
                return proc.returncode
        except subprocess.TimeoutExpired:
            # Stop output writer before adding the terminal error to its log.
            if proc:
                proc.terminate()
                proc.wait(timeout=15)
            if reader:
                reader.join(timeout=5)
            log_file.write(f"\nERROR: ansible-playbook timed out after {timeout_seconds} seconds\n")
            log_file.flush()
            return 124
        finally:
            os.close(parent_write)
            if parent_read is not None:
                os.close(parent_read)
            if proc and proc.poll() is None:
                proc.terminate()
                proc.wait(timeout=15)
            with _PROCESS_LOCK:
                _RUNNING_PROCS.pop(job_id, None)
            if reader:
                reader.join(timeout=5)


def cancel_job(job_id: str) -> bool:
    with _PROCESS_LOCK:
        _CANCELLED_JOBS.add(job_id)
        proc = _RUNNING_PROCS.get(job_id)
        if not proc:
            return True
        proc.terminate()
        return True


def _update_job(job_id: str, **kwargs):
    """Update a job record using a fresh DB session (safe for background tasks)."""
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.job_id == job_id).first()
        if job:
            for key, value in kwargs.items():
                setattr(job, key, value)
            db.commit()
    finally:
        db.close()


def _apply_completion_action(action: dict | None) -> None:
    """Apply database state only after the corresponding remote job succeeds."""
    if not action:
        return
    action_type = action.get("type")
    hostnames = list(dict.fromkeys(action.get("hostnames") or []))
    db = SessionLocal()
    try:
        hosts = db.query(Host).filter(Host.hostname.in_(hostnames)).all() if hostnames else []
        host_ids = {host.id for host in hosts}
        if len(host_ids) != len(hostnames):
            raise RuntimeError("job completion targets no longer match registered devices")

        if action_type == "provision_users":
            for record in action.get("users") or []:
                managed = db.query(ManagedUser).filter(ManagedUser.username == record["username"]).first()
                if not managed:
                    managed = ManagedUser(
                        username=record["username"],
                        full_name=record.get("full_name"),
                        email=record.get("email"),
                        groups="users",
                    )
                    db.add(managed)
                    db.flush()
                else:
                    managed.full_name = record.get("full_name") or managed.full_name
                    managed.email = record.get("email") or managed.email
                for host_id in host_ids:
                    association = db.query(UserHostAssociation).filter(
                        UserHostAssociation.user_id == managed.id,
                        UserHostAssociation.host_id == host_id,
                    ).first()
                    if not association:
                        db.add(UserHostAssociation(user_id=managed.id, host_id=host_id))
        elif action_type in {"update_users", "set_sudoer"}:
            # Observed per-host results below are authoritative, not requested values.
            pass
        elif action_type == "remove_user":
            pass  # Keep per-device absence as an observed result.
        else:
            raise RuntimeError(f"unknown job completion action: {action_type}")
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _process_scan_results(
    target_hostnames: list[str] | None = None,
    unreachable_hosts: set[str] | None = None,
    scan_dir: Path | None = None,
) -> list[str]:
    """Parse scan JSON files written by host_facts.yml and update Host records."""
    scan_dir = scan_dir if scan_dir is not None else settings.data_dir / "scans"

    target_set = set(target_hostnames or [])
    unreachable_hosts = unreachable_hosts or set()
    processed = set()
    warnings = []

    db = SessionLocal()
    try:
        for scan_file in scan_dir.glob("*.json"):
            if scan_file.name.startswith(("storage_", "gpu_usage_", "driver_upgrade_")):
                continue
            try:
                report = json.loads(scan_file.read_text())
                hostname = report.get("hostname")
                if not hostname:
                    continue
                if target_hostnames is not None and hostname not in target_set:
                    continue

                host = db.query(Host).filter(Host.hostname == hostname).first()
                if not host:
                    continue

                host.gpu_model = report.get("gpu_model") or None
                host.driver_version = report.get("driver_version") or None
                host.cuda_version = report.get("cuda_version") or None
                host.os_version = report.get("os_version") or None
                fm_value = report.get("fabric_manager")
                if has_capability(host, NVIDIA_FABRIC_MANAGER) or report.get("fabric_manager_available") is True:
                    host.fabric_manager_status = fm_value if fm_value and fm_value != "N/A" else None
                else:
                    host.fabric_manager_status = None
                host.reboot_required = str(report.get("reboot_required", "false")).lower() in ("true", "yes")
                host.status = "online"
                host.last_seen = datetime.now(timezone.utc)

                # Memory: playbook reports in MB, DB stores GB
                mem_mb = report.get("memory_mb", 0)
                try:
                    host.memory_gb = int(float(mem_mb)) // 1024 if mem_mb else None
                except (ValueError, TypeError):
                    pass

                # Disk percentages
                try:
                    host.disk_root_percent = int(report.get("disk_root_percent", 0))
                except (ValueError, TypeError):
                    host.disk_root_percent = 0
                try:
                    host.disk_raid_percent = int(report.get("disk_raid_percent", 0))
                except (ValueError, TypeError):
                    host.disk_raid_percent = 0

                # NIC info
                nic_info = report.get("nic_info", "")
                if "ConnectX-8" in nic_info or "connectx-8" in nic_info.lower():
                    host.nic_type = "ConnectX-8"
                elif "ConnectX-7" in nic_info or "connectx-7" in nic_info.lower() or "CX7" in nic_info:
                    host.nic_type = "CX7"
                elif nic_info and nic_info != "unknown":
                    host.nic_type = nic_info[:50]
                try:
                    nic_speed = int(report.get("nic_speed_mbps") or 0)
                    host.nic_speed = f"{nic_speed} Mbps" if nic_speed > 0 else None
                except (ValueError, TypeError):
                    host.nic_speed = None

                enrich_from_scan(host, report)

                db.commit()
                processed.add(hostname)
                scan_file.unlink()  # Clean up processed file
            except Exception as exc:
                message = f"Could not process scan report {scan_file.name}: {exc}"
                warnings.append(message)
                logger.warning(message, exc_info=True)

        for hostname in sorted(target_set - processed):
            host = db.query(Host).filter(Host.hostname == hostname).first()
            if not host:
                continue
            host.status = "offline" if hostname in unreachable_hosts else "unknown"
            host.facts_stale = True
        if target_set:
            db.commit()
        # Discovery can change capability groups (GPU, MIG, Fabric Manager,
        # and Kubernetes). Refresh inventory before the next operation uses it.
        if processed:
            regenerate_inventory(db)
    finally:
        db.close()
    return warnings


def job_semaphore() -> asyncio.Semaphore:
    global _JOB_SEMAPHORE
    if _JOB_SEMAPHORE is None:
        _JOB_SEMAPHORE = asyncio.Semaphore(max(1, settings.ansible_max_concurrent_jobs))
    return _JOB_SEMAPHORE


def _resolve_targets(
    db,
    hosts: list[str] | None,
    all_hosts: bool,
    playbook: str,
) -> tuple[list[str] | None, list[str]]:
    if all_hosts and hosts:
        raise PlaybookRequestError("Provide either hosts or all_hosts, not both")
    if all_hosts:
        targets = [
            h.hostname
            for h in db.query(Host)
            .filter((Host.transport == "ssh") | (Host.transport.is_(None)))
            .order_by(Host.hostname)
            .all()
        ]
        if not targets:
            raise PlaybookRequestError("No SSH-managed devices are registered")
        return None, targets
    if hosts is None or len(hosts) == 0:
        raise PlaybookRequestError("Target hosts are required unless all_hosts=true")

    deduped = []
    seen = set()
    for host in hosts:
        if host not in seen:
            deduped.append(host)
            seen.add(host)

    candidates = db.query(Host).filter(Host.hostname.in_(deduped)).all()
    existing = set()
    for host in candidates:
        transport = host.transport or "ssh"
        if transport == "ssh":
            existing.add(host.hostname)
        elif (
            playbook == "reachy_app_reset.yml"
            and transport == "reachy_daemon"
            and host.ansible_user
            and has_capability(host, REACHY_APP_RESET)
        ):
            existing.add(host.hostname)
    missing = [host for host in deduped if host not in existing]
    if missing:
        raise PlaybookRequestError(f"Unknown host target(s): {', '.join(missing)}")
    return deduped, deduped


def _invalidate_devices(targets, *, recovery_reason=None):
    with SessionLocal() as db:
        for host in db.query(Host).filter(Host.hostname.in_(targets)).all():
            host.facts_stale = True
            for association in db.query(UserHostAssociation).filter_by(host_id=host.id).all():
                association.state = "unverified"
            if recovery_reason:
                host.recovery_required = True
                host.recovery_reason = recovery_reason
        db.commit()


def _reconcile_accounts(job_id, targets):
    from backend.services.account_state import reconcile_accounts
    with SessionLocal() as db:
        reconcile_accounts(db, get_job_results(job_id), targets)


async def run_playbook(
    db, playbook: str, hosts: list[str] | None = None, all_hosts: bool = False,
    extra_vars: dict | None = None, triggered_by: str = "admin",
    completion_action: dict | None = None, request_key: str | None = None,
) -> str:
    """Reserve exact devices durably before accepting any execution request."""
    if playbook not in ALLOWED_PLAYBOOKS:
        raise PlaybookRequestError(f"Unsupported playbook: {playbook}")
    _validate_extra_vars(extra_vars or {})
    hosts, targets = _resolve_targets(db, hosts, all_hosts, playbook)
    fingerprint = request_fingerprint(playbook, targets, extra_vars)
    if request_key:
        previous = db.query(Job).filter_by(request_key=request_key).first()
        if previous:
            if previous.request_fingerprint != fingerprint:
                raise PlaybookRequestError("Request key already used for a different operation", 409)
            return previous.job_id
    devices = db.query(Host).filter(Host.hostname.in_(targets)).all()
    host_credentials = {}
    for host in devices:
        credentials = {}
        for key, encrypted in (("ansible_password", host.encrypted_ansible_password), ("ansible_become_password", host.encrypted_ansible_become_password)):
            if encrypted:
                credentials[key] = decrypt_secret(encrypted)
        host_credentials[host.hostname] = credentials
    daemon_targets = {host.hostname: (host.endpoint or host.hostname, host.daemon_port or 8000) for host in devices if host.transport == "reachy_daemon"}
    readonly = is_read_only(playbook, extra_vars)
    recovery = playbook == "recovery_check.yml" or (playbook == "host_drain.yml" and (extra_vars or {}).get("drain_action") == "resume")
    job_id = str(uuid.uuid4())
    job = Job(job_id=job_id, playbook=playbook, target_hosts=",".join(targets),
              status="pending", phase="queued", execution_kind="read_only" if readonly else "mutation",
              triggered_by=triggered_by, extra_vars=redact_extra_vars(extra_vars or {}),
              request_key=request_key, request_fingerprint=fingerprint)
    try:
        reserve_devices(db, job, devices, recovery=recovery)
    except ExecutionConflict as exc:
        raise PlaybookRequestError(str(exc), 409) from exc

    async def _run():
        log_path = get_log_path(job_id)
        started = False
        try:
            async with job_semaphore():
                if job_id in _CANCELLED_JOBS:
                    _update_job(job_id, status="cancelled", phase="cancelled", finished_at=datetime.now(timezone.utc))
                    return
                started_at = datetime.now(timezone.utc)
                _update_job(job_id, status="running", phase="executing", started_at=started_at)
                started = True
                if not readonly:
                    _invalidate_devices(targets)
                rc = await _execute(playbook, targets, extra_vars,
                                              host_credentials, job_id, settings.ansible_job_timeout_seconds)
                output = log_path.read_text() if log_path.exists() else ""
                outcomes = parse_host_outcomes(output, targets)
                successful = [item["hostname"] for item in outcomes if item["status"] == "success"]
                failed = [name for name in targets if name not in successful]
                cancelled = job_id in _CANCELLED_JOBS
                errors = []
                if rc or failed:
                    errors.append("One or more devices did not complete. Review per-device outcomes and the log.")
                if rc == 124:
                    errors.append(f"Timed out after {settings.ansible_job_timeout_seconds} seconds.")
                if completion_action and successful:
                    _apply_completion_action({**completion_action, "hostnames": successful})
                # Access reports are collected even when other hosts fail.
                _reconcile_accounts(job_id, targets)
                if playbook == "host_facts.yml":
                    errors.extend(_process_scan_results(targets, _extract_unreachable_hosts(output), settings.data_dir / "scans" / job_id))
                    with SessionLocal() as state_db:
                        for host in state_db.query(Host).filter(Host.hostname.in_(successful)).all():
                            if host.facts_stale:
                                failed.append(host.hostname)
                                errors.append(f"{host.hostname}: scan report missing or invalid")
                elif playbook == "reachy_app_reset.yml" and successful:
                    from backend.services.device_discovery import probe_reachy
                    for name in successful:
                        result = await asyncio.to_thread(probe_reachy, *daemon_targets[name]) if name in daemon_targets else None
                        if result and result["reachable"]:
                            with SessionLocal() as state_db:
                                host = state_db.query(Host).filter_by(hostname=name).one()
                                host.facts = result.get("facts", {})
                                host.facts_stale = False
                                host.discovered_at = datetime.now(timezone.utc)
                                host.last_seen = host.discovered_at
                                state_db.commit()
                        else:
                            failed.append(name)
                            errors.append(f"{name}: refresh daemon health after app reset")
                elif (not readonly or recovery) and successful:
                    _update_job(job_id, phase="refreshing_facts")
                    for name in successful:
                        (settings.data_dir / "scans" / job_id / f"{name}.json").unlink(missing_ok=True)
                    # Append the follow-up scan output without replacing the action log.
                    scan_rc = await _execute("host_facts.yml", successful, None,
                                                       host_credentials, job_id, settings.ansible_job_timeout_seconds, True)
                    scan_output = log_path.read_text() if log_path.exists() else ""
                    output = scan_output
                    errors.extend(_process_scan_results(successful, _extract_unreachable_hosts(scan_output.split("--- Post-operation facts ---")[-1]), settings.data_dir / "scans" / job_id))
                    with SessionLocal() as state_db:
                        unverified = {host.hostname for host in state_db.query(Host).filter(Host.hostname.in_(successful)).all() if host.facts_stale}
                    if scan_rc or unverified:
                        errors.append("Post-operation facts could not be fully verified. Scan and verify recovery before further changes.")
                        for item in outcomes:
                            if item["hostname"] in unverified:
                                item["status"] = "verification_failed"
                                failed.append(item["hostname"])
                if not readonly and (failed or rc):
                    _invalidate_devices(failed or targets, recovery_reason=f"Incomplete job {job_id} ({playbook})")
                if recovery:
                    with SessionLocal() as state_db:
                        verified = [item["hostname"] for item in outcomes if item["status"] == "success"]
                        for host in state_db.query(Host).filter(Host.hostname.in_(verified)).all():
                            if not host.facts_stale:
                                host.recovery_required = False
                                host.recovery_reason = None
                        state_db.commit()
                finished = datetime.now(timezone.utc)
                status = "success" if rc == 0 and not failed and not errors else "failed"
                if not readonly and (failed or rc):
                    status = "recovery_required"
                elif cancelled:
                    status = "cancelled"
                _update_job(job_id, status=status, phase="complete", finished_at=finished,
                            duration_seconds=int((finished - started_at).total_seconds()), output_log=output,
                            recap=_extract_recap(output), outcomes_json=json.dumps(outcomes),
                            error_summary="\n".join(errors) or None)
        except (Exception, asyncio.CancelledError) as exc:
            uncertain = started and not readonly
            if uncertain:
                _invalidate_devices(targets, recovery_reason=f"Interrupted job {job_id} ({playbook})")
            logger.warning("Job %s interrupted: %s", job_id, exc, exc_info=True)
            _update_job(job_id, status="recovery_required" if uncertain else ("cancelled" if not started or job_id in _CANCELLED_JOBS else "failed"), phase="interrupted",
                        finished_at=datetime.now(timezone.utc), error_summary="Execution interrupted; inspect remote state and verify recovery." if uncertain else ("Executor stopped before this queued job began" if not started else str(exc)[:2000]),
                        output_log=log_path.read_text() if log_path.exists() else "")
        finally:
            # Wait for a thread-backed process to stop before releasing its devices.
            with _PROCESS_LOCK:
                proc = _RUNNING_PROCS.get(job_id)
                if proc:
                    proc.terminate()
            if proc:
                await asyncio.to_thread(proc.wait, timeout=15)
            _CANCELLED_JOBS.discard(job_id)
            with SessionLocal() as state_db:
                release_devices(state_db, job_id)
                state_db.commit()
            try:
                await asyncio.to_thread(job_log_indexer.ingest_completed_job, job_id)
            except Exception:
                logger.exception("Failed to index completed job %s", job_id)
                job_log_indexer.start_reconcile()

    track_task(_run())
    return job_id
