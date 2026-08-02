import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.auth import get_current_user
from backend.capabilities import FABRIC_MANAGER_MACHINE_TYPES
from backend.config import settings
from backend.database import get_db
from backend.models import Host, Job
from backend.schemas import DiskUsageResponse, MaintenanceOverviewResponse, MaintenanceRequest
from backend.services.ansible_runner import run_playbook

router = APIRouter(prefix="/api/v1/maintenance", tags=["maintenance"])
logger = logging.getLogger(__name__)

GPU_REPORT_STALE_SECONDS = 30 * 60
STORAGE_REPORT_STALE_SECONDS = 24 * 60 * 60
HOST_SCAN_STALE_SECONDS = 24 * 60 * 60
DISK_WARN_PCT = 85


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _iso(dt: datetime | None) -> str | None:
    if not dt:
        return None
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _file_timestamp(path: Path) -> datetime:
    return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)


def _report_timestamp(path: Path, report: dict) -> datetime:
    raw = report.get("timestamp")
    if raw:
        try:
            return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).astimezone(timezone.utc)
        except ValueError:
            pass
    return _file_timestamp(path)


def _freshness(timestamps: list[datetime], stale_after_seconds: int, now: datetime) -> dict:
    if not timestamps:
        return {"last_scanned_at": None, "age_seconds": None, "stale": True}
    latest = max(timestamps)
    age = max(0, int((now - latest).total_seconds()))
    return {
        "last_scanned_at": _iso(latest),
        "age_seconds": age,
        "stale": age > stale_after_seconds,
    }


def _read_cached_reports(prefix: str) -> list[tuple[Path, dict, datetime]]:
    scan_dir = settings.data_dir / "scans"
    reports = []
    if not scan_dir.exists():
        return reports
    for scan_file in sorted(scan_dir.glob(f"{prefix}_*.json")):
        try:
            report = json.loads(scan_file.read_text())
            reports.append((scan_file, report, _report_timestamp(scan_file, report)))
        except Exception:
            logger.warning("Could not read cached %s report %s", prefix, scan_file, exc_info=True)
            continue
    return reports


def _safe_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


async def _run_maintenance_job(
    *,
    db: Session,
    playbook: str,
    user: str,
    hosts: list[str] | None = None,
    all_hosts: bool = False,
    extra_vars: dict | None = None,
    detail: str,
):
    job_id = await run_playbook(
        db=db,
        playbook=playbook,
        hosts=hosts,
        all_hosts=all_hosts,
        extra_vars=extra_vars,
        triggered_by=user,
    )
    return {"job_id": job_id, "detail": detail}


@router.post("/package-update")
async def run_package_update(
    payload: MaintenanceRequest | None = None,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    hosts = payload.hosts if payload else None
    all_hosts = payload.all_hosts if payload else False
    return await _run_maintenance_job(
        db=db,
        playbook="system_maintenance.yml",
        user=user,
        hosts=hosts,
        all_hosts=all_hosts,
        detail="Package update started",
    )


@router.post("/docker-cleanup")
async def run_docker_cleanup(
    payload: MaintenanceRequest | None = None,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    hosts = payload.hosts if payload else None
    all_hosts = payload.all_hosts if payload else False
    return await _run_maintenance_job(
        db=db,
        playbook="docker_cleanup.yml",
        user=user,
        hosts=hosts,
        all_hosts=all_hosts,
        detail="Docker cleanup started",
    )


@router.post("/preflight-check")
async def run_preflight_check(
    payload: MaintenanceRequest | None = None,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    hosts = payload.hosts if payload else None
    all_hosts = payload.all_hosts if payload else False
    return await _run_maintenance_job(
        db=db,
        playbook="preflight_check.yml",
        user=user,
        hosts=hosts,
        all_hosts=all_hosts,
        detail="Preflight check started",
    )


@router.post("/health-diagnostics")
async def run_health_diagnostics(
    payload: MaintenanceRequest | None = None,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    hosts = payload.hosts if payload else None
    all_hosts = payload.all_hosts if payload else False
    return await _run_maintenance_job(
        db=db,
        playbook="health_diagnostics.yml",
        user=user,
        hosts=hosts,
        all_hosts=all_hosts,
        detail="Health diagnostics started",
    )


@router.post("/host-bootstrap")
async def run_host_bootstrap(
    payload: MaintenanceRequest | None = None,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    hosts = payload.hosts if payload else None
    all_hosts = payload.all_hosts if payload else False
    return await _run_maintenance_job(
        db=db,
        playbook="host_bootstrap.yml",
        user=user,
        hosts=hosts,
        all_hosts=all_hosts,
        detail="Host bootstrap started",
    )


@router.post("/firmware-inventory")
async def run_firmware_inventory(
    payload: MaintenanceRequest | None = None,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    hosts = payload.hosts if payload else None
    all_hosts = payload.all_hosts if payload else False
    return await _run_maintenance_job(
        db=db,
        playbook="firmware_inventory.yml",
        user=user,
        hosts=hosts,
        all_hosts=all_hosts,
        detail="Firmware inventory started",
    )


@router.post("/firmware-update")
async def run_firmware_update(
    payload: MaintenanceRequest | None = None,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    hosts = payload.hosts if payload else None
    all_hosts = payload.all_hosts if payload else False
    return await _run_maintenance_job(
        db=db,
        playbook="firmware_update.yml",
        user=user,
        hosts=hosts,
        all_hosts=all_hosts,
        extra_vars={"firmware_mode": "update"},
        detail="Firmware update started",
    )


@router.post("/drain/{action}")
async def run_drain_action(
    action: str,
    payload: MaintenanceRequest | None = None,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if action not in ("status", "drain", "resume"):
        raise HTTPException(status_code=400, detail=f"Invalid drain action: {action}")
    hosts = payload.hosts if payload else None
    all_hosts = payload.all_hosts if payload else False
    return await _run_maintenance_job(
        db=db,
        playbook="host_drain.yml",
        user=user,
        hosts=hosts,
        all_hosts=all_hosts,
        extra_vars={"drain_action": action},
        detail=f"Host drain action started: {action}",
    )


@router.post("/mig/{action}")
async def run_mig_action(
    action: str,
    payload: MaintenanceRequest | None = None,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if action not in ("status", "enable", "disable"):
        raise HTTPException(status_code=400, detail=f"Invalid MIG action: {action}")

    hosts = payload.hosts if payload else None
    all_hosts = payload.all_hosts if payload else False
    if hosts:
        invalid = (
            db.query(Host.hostname)
            .filter(
                Host.hostname.in_(hosts),
                or_(
                    Host.machine_type.is_(None),
                    ~Host.machine_type.in_(FABRIC_MANAGER_MACHINE_TYPES),
                ),
            )
            .all()
        )
        if invalid:
            names = [h.hostname for h in invalid]
            raise HTTPException(
                status_code=400,
                detail=f"MIG controls are only enabled for DGX Workstation hosts: {', '.join(names)}",
            )

    return await _run_maintenance_job(
        db=db,
        playbook="mig_management.yml",
        user=user,
        hosts=hosts,
        all_hosts=all_hosts,
        extra_vars={"mig_action": action},
        detail=f"MIG action started: {action}",
    )


@router.get("/reboot-required")
def get_reboot_required(
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    hosts = db.query(Host).filter(Host.reboot_required == True).order_by(Host.hostname).all()
    return [{"hostname": h.hostname, "machine_type": h.machine_type} for h in hosts]


@router.get("/overview", response_model=MaintenanceOverviewResponse)
def get_maintenance_overview(
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    """Return the operator-focused 80% maintenance summary for the dashboard."""
    now = _utc_now()
    hosts = db.query(Host).order_by(Host.hostname).all()
    active_jobs = (
        db.query(Job)
        .filter(Job.status.in_(("running", "pending")))
        .order_by(Job.created_at.desc())
        .limit(10)
        .all()
    )

    stale_hosts = []
    high_disk_hosts = []
    for host in hosts:
        last_seen = _as_aware_utc(host.last_seen)
        if host.status == "online":
            if last_seen is None:
                stale_hosts.append(host.hostname)
            else:
                age = int((now - last_seen).total_seconds())
                if age > HOST_SCAN_STALE_SECONDS:
                    stale_hosts.append(host.hostname)

        max_disk = max(host.disk_root_percent or 0, host.disk_raid_percent or 0)
        if max_disk >= DISK_WARN_PCT:
            high_disk_hosts.append({
                "hostname": host.hostname,
                "root_pct": host.disk_root_percent or 0,
                "raid_pct": host.disk_raid_percent or 0,
                "max_pct": max_disk,
            })

    gpu_reports = _read_cached_reports("gpu_usage")
    gpu_timestamps = [ts for _, _, ts in gpu_reports]
    gpu_users: dict[str, dict] = {}
    gpu_hosts = []
    gpu_totals = {"total_gpus": 0, "free_gpus": 0, "idle_gpus": 0, "active_gpus": 0}
    unknown_gpu_processes = 0

    for _, report, _ in gpu_reports:
        hostname = report.get("hostname") or "unknown"
        host_unknown = 0
        for key in gpu_totals:
            gpu_totals[key] += _safe_int(report.get(key))

        for gpu in report.get("gpus", []) or []:
            for proc in gpu.get("processes", []) or []:
                if proc.get("user", "unknown") in ("", "unknown"):
                    unknown_gpu_processes += 1
                    host_unknown += 1

        for summary in report.get("user_summary", []) or []:
            name = summary.get("user") or "unknown"
            entry = gpu_users.setdefault(
                name,
                {"user": name, "gpu_count": 0, "total_memory_mb": 0, "hosts": set()},
            )
            entry["gpu_count"] += _safe_int(summary.get("gpu_count"))
            entry["total_memory_mb"] += _safe_int(summary.get("total_memory_mb"))
            entry["hosts"].add(hostname)

        gpu_hosts.append({
            "hostname": hostname,
            "total_gpus": _safe_int(report.get("total_gpus")),
            "free_gpus": _safe_int(report.get("free_gpus")),
            "idle_gpus": _safe_int(report.get("idle_gpus")),
            "active_gpus": _safe_int(report.get("active_gpus")),
            "unknown_processes": host_unknown,
        })

    gpu_user_list = []
    for entry in gpu_users.values():
        gpu_user_list.append({
            "user": entry["user"],
            "gpu_count": entry["gpu_count"],
            "total_memory_mb": entry["total_memory_mb"],
            "hosts": sorted(entry["hosts"]),
        })
    gpu_user_list.sort(key=lambda item: (item["gpu_count"], item["total_memory_mb"]), reverse=True)
    gpu_hosts.sort(key=lambda item: (item["active_gpus"], item["idle_gpus"], item["hostname"]), reverse=True)

    storage_reports = _read_cached_reports("storage")
    storage_timestamps = [ts for _, _, ts in storage_reports]
    pressure_by_key: dict[tuple[str, str], dict] = {}
    owner_entries = []

    def add_pressure(hostname: str, mountpoint: str, mount_type: str | None, use_pct: int, used_mb=None, total_mb=None):
        if use_pct < DISK_WARN_PCT:
            return
        pressure_by_key[(hostname, mountpoint)] = {
            "hostname": hostname,
            "mountpoint": mountpoint,
            "mount_type": mount_type,
            "use_pct": use_pct,
            "used_mb": _safe_int(used_mb, 0) if used_mb is not None else None,
            "total_mb": _safe_int(total_mb, 0) if total_mb is not None else None,
        }

    def add_owner_entry(hostname: str, mountpoint: str, mount_type: str | None, use_pct: int | None, entry: dict):
        size_mb = _safe_int(entry.get("size_mb"))
        if size_mb <= 0:
            return
        name = str(entry.get("name") or "").strip("/")
        path = entry.get("path")
        if not path:
            base = mountpoint.rstrip("/") or "/"
            path = f"{base}/{name}" if name else base
        owner_entries.append({
            "hostname": hostname,
            "owner_user": entry.get("owner_user"),
            "owner_uid": entry.get("owner_uid"),
            "owner_group": entry.get("owner_group"),
            "path": path,
            "size_mb": size_mb,
            "mountpoint": mountpoint,
            "mount_type": mount_type,
            "use_pct": use_pct,
            "kind": entry.get("kind") or "directory",
        })

    for _, report, _ in storage_reports:
        hostname = report.get("hostname") or "unknown"
        mounts = report.get("mounts") or []
        for mount in mounts:
            mountpoint = mount.get("mountpoint") or "/"
            if any(mountpoint.startswith(p) for p in _MOUNT_SKIP_PREFIXES):
                continue
            mount_type = mount.get("type")
            use_pct = _safe_int(mount.get("use_pct"))
            add_pressure(hostname, mountpoint, mount_type, use_pct, mount.get("used_mb"), mount.get("total_mb"))
            for entry in mount.get("entries", []) or []:
                add_owner_entry(hostname, mountpoint, mount_type, use_pct, entry)

        for entry in report.get("home_entries", []) or []:
            add_owner_entry(hostname, "/home", "home", None, entry)
        if not mounts:
            for entry in report.get("raid_entries", []) or []:
                add_owner_entry(hostname, "/raid", "raid", None, entry)

    for host in hosts:
        add_pressure(host.hostname, "/", "root", host.disk_root_percent or 0)
        if host.disk_raid_percent:
            add_pressure(host.hostname, "/raid", "raid", host.disk_raid_percent)

    owner_entries.sort(key=lambda item: item["size_mb"], reverse=True)
    pressure_hosts = sorted(
        pressure_by_key.values(),
        key=lambda item: (item["use_pct"], item["hostname"], item["mountpoint"]),
        reverse=True,
    )

    return {
        "generated_at": now,
        "fleet": {
            "total_hosts": len(hosts),
            "online_hosts": sum(1 for h in hosts if h.status == "online"),
            "offline_hosts": sum(1 for h in hosts if h.status == "offline"),
            "unknown_hosts": sum(1 for h in hosts if h.status == "unknown"),
            "reboot_required_hosts": [h.hostname for h in hosts if h.reboot_required],
            "stale_hosts": stale_hosts,
            "high_disk_hosts": high_disk_hosts,
            "active_jobs": [
                {
                    "job_id": job.job_id,
                    "playbook": job.playbook,
                    "target_hosts": job.target_hosts,
                    "status": job.status,
                }
                for job in active_jobs
            ],
        },
        "gpu": {
            **_freshness(gpu_timestamps, GPU_REPORT_STALE_SECONDS, now),
            **gpu_totals,
            "hosts": gpu_hosts,
            "users": gpu_user_list[:10],
            "unknown_processes": unknown_gpu_processes,
        },
        "storage": {
            **_freshness(storage_timestamps, STORAGE_REPORT_STALE_SECONDS, now),
            "pressure_hosts": pressure_hosts[:10],
            "owners": owner_entries[:20],
            "unknown_owner_entries": sum(1 for e in owner_entries if not e.get("owner_user")),
        },
    }


@router.post("/reboot")
async def reboot_hosts(
    payload: MaintenanceRequest | None = None,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    extra_vars = {}
    if payload and payload.hosts:
        # Specific hosts requested — force reboot regardless of reboot-required flag
        target_hosts = payload.hosts
        extra_vars["force_reboot"] = True
        all_hosts = False
    elif payload and payload.all_hosts:
        # Default to all hosts that need a reboot
        hosts_needing_reboot = db.query(Host).filter(Host.reboot_required == True).all()
        target_hosts = [h.hostname for h in hosts_needing_reboot]
        all_hosts = False
    else:
        raise HTTPException(status_code=400, detail="Select reboot hosts or set all_hosts=true")

    if not target_hosts:
        return {"detail": "No hosts require a reboot"}

    job_id = await run_playbook(
        db=db,
        playbook="reboot.yml",
        hosts=target_hosts,
        all_hosts=all_hosts,
        extra_vars=extra_vars,
        triggered_by=user,
    )
    return {"job_id": job_id, "detail": f"Rebooting {len(target_hosts)} host(s): {', '.join(target_hosts)}"}


@router.post("/storage-analysis")
async def run_storage_analysis(
    payload: MaintenanceRequest | None = None,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    hosts = payload.hosts if payload else None
    all_hosts = payload.all_hosts if payload else False
    job_id = await run_playbook(
        db=db,
        playbook="storage_analysis.yml",
        hosts=hosts,
        all_hosts=all_hosts,
        triggered_by=user,
    )
    return {"job_id": job_id, "detail": "Storage analysis started"}


_MOUNT_SKIP_PREFIXES = ("/var/lib/kubelet/", "/var/lib/docker/", "/var/lib/containerd/",
                        "/snap/", "/sys/", "/proc/", "/run/")


@router.get("/storage-analysis")
def get_storage_analysis(
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    """Return cached storage analysis results from the most recent scan."""
    scan_dir = settings.data_dir / "scans"
    results = []
    if scan_dir.exists():
        for scan_file in scan_dir.glob("storage_*.json"):
            try:
                report = json.loads(scan_file.read_text())
                # Filter out kubelet/container volume mounts from cached data
                if "mounts" in report:
                    report["mounts"] = [
                        m for m in report["mounts"]
                        if not any(m.get("mountpoint", "").startswith(p) for p in _MOUNT_SKIP_PREFIXES)
                    ]
                results.append(report)
            except Exception:
                logger.warning("Could not read storage analysis report %s", scan_file, exc_info=True)
                continue
    return results


@router.post("/gpu-usage")
async def run_gpu_usage(
    payload: MaintenanceRequest | None = None,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    hosts = payload.hosts if payload else None
    all_hosts = payload.all_hosts if payload else False
    job_id = await run_playbook(
        db=db,
        playbook="gpu_usage.yml",
        hosts=hosts,
        all_hosts=all_hosts,
        triggered_by=user,
    )
    return {"job_id": job_id, "detail": "GPU usage analysis started"}


@router.get("/gpu-usage")
def get_gpu_usage(
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    """Return cached GPU usage results from the most recent scan."""
    scan_dir = settings.data_dir / "scans"
    results = []
    if scan_dir.exists():
        for scan_file in scan_dir.glob("gpu_usage_*.json"):
            try:
                report = json.loads(scan_file.read_text())
                results.append(report)
            except Exception:
                logger.warning("Could not read GPU usage report %s", scan_file, exc_info=True)
                continue
    return results


@router.get("/disk-usage", response_model=list[DiskUsageResponse])
def get_disk_usage(
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    hosts = db.query(Host).order_by(Host.hostname).all()
    return [
        DiskUsageResponse(
            hostname=h.hostname,
            disk_root_percent=h.disk_root_percent,
            disk_raid_percent=h.disk_raid_percent,
        )
        for h in hosts
    ]
