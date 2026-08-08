import asyncio
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
from backend.models import Host, Job
from backend.services import job_log_indexer
from backend.capabilities import NVIDIA_FABRIC_MANAGER, has_capability
from backend.services.device_discovery import enrich_from_scan
from backend.services.inventory_writer import regenerate_inventory
from backend.services.secret_store import decrypt_secret

logger = logging.getLogger(__name__)

SENSITIVE_KEYS = {"password", "new_password", "temp_password", "default_password"}
SENSITIVE_KEY_PARTS = ("password", "secret", "token", "api_key")
JINJA_MARKERS = ("{{", "}}", "{%", "%}", "{#", "#}")
FLEET_CREDENTIALS_VAR = "__fleet_host_credentials"
RESERVED_EXTRA_VARS = {
    FLEET_CREDENTIALS_VAR,
    "ansible_password",
    "ansible_ssh_pass",
    "ansible_become_password",
    "ansible_become_pass",
}
ALLOWED_PLAYBOOKS = {
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
    "mig_management.yml",
    "preflight_check.yml",
    "reboot.yml",
    "remove_sudoers.yml",
    "remove_user.yml",
    "setup_kubeconfig.yml",
    "storage_analysis.yml",
    "system_maintenance.yml",
    "user_management.yml",
}

_PROCESS_LOCK = threading.Lock()
_RUNNING_PROCS: dict[str, subprocess.Popen] = {}
_CANCELLED_JOBS: set[str] = set()
_HOST_LOCKS: dict[str, asyncio.Lock] = {}
_HOST_LOCKS_GUARD = asyncio.Lock()
_JOB_SEMAPHORE: asyncio.Semaphore | None = None


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
) -> int:
    """Run ansible-playbook, streaming output to a log file line by line. Returns rc."""
    ansible_dir = settings.ansible_dir
    log_path = get_log_path(job_id)

    env_vars = {
        "ANSIBLE_CONFIG": str(ansible_dir / "ansible.cfg"),
        "ANSIBLE_INVENTORY": str(settings.resolved_inventory_file),
        "ANSIBLE_ROLES_PATH": str(ansible_dir / "roles"),
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

    log_fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(log_fd, "w") as log_file:
        payload = dict(extra_vars or {})
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
        extra_vars_dir = None
        try:
            if payload:
                extra_vars_dir = tempfile.TemporaryDirectory(prefix="fleet-extra-vars-")
                extra_vars_path = Path(extra_vars_dir.name) / "payload.json"
                os.mkfifo(extra_vars_path, 0o600)
                cmd.extend(["--extra-vars", f"@{extra_vars_path}"])

            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=env_vars,
                cwd=str(ansible_dir),
            )

            if payload:
                try:
                    with extra_vars_path.open("w") as pipe:
                        json.dump(payload, pipe, allow_nan=False)
                except BrokenPipeError:
                    pass
        finally:
            if extra_vars_dir is not None:
                extra_vars_dir.cleanup()

        with _PROCESS_LOCK:
            _RUNNING_PROCS[job_id] = proc

        def _copy_output():
            assert proc.stdout is not None
            for line in proc.stdout:
                log_file.write(_redact_output_line(line, secrets))
                log_file.flush()

        reader = threading.Thread(target=_copy_output, daemon=True)
        reader.start()
        try:
            proc.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            log_file.write(f"\nERROR: ansible-playbook timed out after {timeout_seconds} seconds\n")
            log_file.flush()
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            return 124
        finally:
            with _PROCESS_LOCK:
                _RUNNING_PROCS.pop(job_id, None)
            reader.join(timeout=5)

        return proc.returncode


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


def _process_scan_results(
    target_hostnames: list[str] | None = None,
    unreachable_hosts: set[str] | None = None,
) -> list[str]:
    """Parse scan JSON files written by host_facts.yml and update Host records."""
    scan_dir = settings.data_dir / "scans"
    if not scan_dir.exists():
        return []

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
        if target_set:
            db.commit()
        # Discovery can change capability groups (GPU, MIG, Fabric Manager,
        # and Kubernetes). Refresh inventory before the next operation uses it.
        if processed:
            regenerate_inventory(db)
    finally:
        db.close()
    return warnings


def _job_semaphore() -> asyncio.Semaphore:
    global _JOB_SEMAPHORE
    if _JOB_SEMAPHORE is None:
        _JOB_SEMAPHORE = asyncio.Semaphore(max(1, settings.ansible_max_concurrent_jobs))
    return _JOB_SEMAPHORE


async def _acquire_host_locks(targets: list[str]) -> list[asyncio.Lock]:
    async with _HOST_LOCKS_GUARD:
        locks = [_HOST_LOCKS.setdefault(host, asyncio.Lock()) for host in sorted(set(targets))]
    acquired = []
    try:
        for lock in locks:
            await lock.acquire()
            acquired.append(lock)
        return acquired
    except Exception:
        for lock in reversed(acquired):
            lock.release()
        raise


def _release_host_locks(locks: list[asyncio.Lock]) -> None:
    for lock in reversed(locks):
        if lock.locked():
            lock.release()


def _resolve_targets(db, hosts: list[str] | None, all_hosts: bool) -> tuple[list[str] | None, list[str]]:
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

    existing = {
        h.hostname
        for h in db.query(Host.hostname)
        .filter(
            Host.hostname.in_(deduped),
            (Host.transport == "ssh") | (Host.transport.is_(None)),
        )
        .all()
    }
    missing = [host for host in deduped if host not in existing]
    if missing:
        raise PlaybookRequestError(f"Unknown host target(s): {', '.join(missing)}")
    return deduped, deduped


async def run_playbook(
    db,
    playbook: str,
    hosts: list[str] | None = None,
    all_hosts: bool = False,
    extra_vars: dict | None = None,
    triggered_by: str = "admin",
) -> str:
    """Queue and run an Ansible playbook. Returns the job_id."""
    if playbook not in ALLOWED_PLAYBOOKS:
        raise PlaybookRequestError(f"Unsupported playbook: {playbook}")
    _validate_extra_vars(extra_vars or {})

    hosts, lock_targets = _resolve_targets(db, hosts, all_hosts)
    registered_hosts = {
        host.hostname: host
        for host in db.query(Host).filter(Host.hostname.in_(lock_targets)).all()
    }
    host_credentials = {}
    for hostname in lock_targets:
        host = registered_hosts[hostname]
        credentials = {}
        ansible_password = decrypt_secret(host.encrypted_ansible_password)
        become_password = decrypt_secret(host.encrypted_ansible_become_password)
        if ansible_password:
            credentials["ansible_password"] = ansible_password
        if become_password:
            credentials["ansible_become_password"] = become_password
        host_credentials[hostname] = credentials

    job_id = str(uuid.uuid4())
    limit = ",".join(lock_targets)
    started_at = datetime.now(timezone.utc)
    scan_targets = None
    if playbook == "host_facts.yml":
        if hosts is not None:
            scan_targets = list(hosts)
        else:
            scan_targets = list(lock_targets)

    job = Job(
        job_id=job_id,
        playbook=playbook,
        target_hosts=limit,
        status="pending",
        started_at=started_at,
        triggered_by=triggered_by,
        extra_vars=redact_extra_vars(extra_vars or {}),
    )
    db.add(job)
    db.commit()

    async def _run():
        log_path = get_log_path(job_id)
        locks: list[asyncio.Lock] = []
        try:
            if job_id in _CANCELLED_JOBS:
                _update_job(
                    job_id,
                    status="cancelled",
                    finished_at=datetime.now(timezone.utc),
                    error_summary="Cancellation requested before job started",
                )
                return
            async with _job_semaphore():
                if job_id in _CANCELLED_JOBS:
                    _update_job(
                        job_id,
                        status="cancelled",
                        finished_at=datetime.now(timezone.utc),
                        error_summary="Cancellation requested before job started",
                    )
                    return
                locks = await _acquire_host_locks(lock_targets)
                if job_id in _CANCELLED_JOBS:
                    _update_job(
                        job_id,
                        status="cancelled",
                        finished_at=datetime.now(timezone.utc),
                        error_summary="Cancellation requested before job started",
                    )
                    return
                _update_job(job_id, status="running")
                rc = await asyncio.to_thread(
                    _run_playbook_streaming,
                    playbook,
                    lock_targets,
                    extra_vars,
                    host_credentials,
                    job_id,
                    settings.ansible_job_timeout_seconds,
                )
            finished = datetime.now(timezone.utc)
            duration = int((finished - started_at).total_seconds())

            output = log_path.read_text() if log_path.exists() else ""

            recap = _extract_recap(output)
            was_cancelled = job_id in _CANCELLED_JOBS

            update_kwargs = {
                "status": "cancelled" if was_cancelled else ("success" if rc == 0 else "failed"),
                "finished_at": finished,
                "duration_seconds": duration,
                "output_log": output,
                "recap": recap,
            }
            if was_cancelled:
                update_kwargs["error_summary"] = "Cancellation requested by operator"
            elif rc == 124:
                update_kwargs["error_summary"] = f"Timed out after {settings.ansible_job_timeout_seconds} seconds"
            elif rc != 0:
                update_kwargs["error_summary"] = output[-2000:] if output else "Unknown error"

            _update_job(job_id, **update_kwargs)

            # Parse scan results after host scans. For all-host scans, keep
            # partial successes and mark explicit unreachable hosts offline.
            if playbook == "host_facts.yml":
                try:
                    warnings = _process_scan_results(
                        target_hostnames=scan_targets,
                        unreachable_hosts=_extract_unreachable_hosts(output),
                    )
                    if warnings:
                        _update_job(job_id, error_summary="\n".join(warnings[:10]))
                except Exception:
                    logger.exception("Failed to update host scan results for job %s", job_id)
                    _update_job(job_id, error_summary="Failed to update host scan results; see server logs")
            elif playbook == "host_bootstrap.yml" and rc == 0:
                try:
                    warnings = _process_scan_results()
                    if warnings:
                        _update_job(job_id, error_summary="\n".join(warnings[:10]))
                except Exception:
                    logger.exception("Failed to update bootstrap scan results for job %s", job_id)
                    _update_job(job_id, error_summary="Failed to update bootstrap scan results; see server logs")

        except Exception as e:
            # Read whatever was written so far
            output = log_path.read_text() if log_path.exists() else ""
            logger.exception("Ansible job %s failed before completion", job_id)
            _update_job(
                job_id,
                status="failed",
                finished_at=datetime.now(timezone.utc),
                error_summary=str(e)[:2000],
                output_log=output or str(e),
            )
        finally:
            _CANCELLED_JOBS.discard(job_id)
            _release_host_locks(locks)
            try:
                # Job-log retrieval is derived state. Index every terminal
                # outcome after releasing host locks, and never let an
                # embedding/Milvus outage change the recorded job result.
                await asyncio.to_thread(job_log_indexer.ingest_completed_job, job_id)
            except Exception:
                logger.exception("Failed to index completed Ansible job %s", job_id)
                job_log_indexer.start_reconcile()

    asyncio.create_task(_run())
    return job_id
