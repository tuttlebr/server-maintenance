from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.auth import get_current_user
from backend.capabilities import GPU_MACHINE_TYPES
from backend.database import get_db
from backend.models import Host
from backend.schemas import DriverStatusResponse, DriverUpgradeRequest
from backend.services.ansible_runner import run_playbook

router = APIRouter(prefix="/api/v1/drivers", tags=["drivers"])


@router.get("/", response_model=list[DriverStatusResponse])
def get_driver_status(
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    hosts = (
        db.query(Host)
        .filter(Host.machine_type.in_(GPU_MACHINE_TYPES))
        .order_by(Host.hostname)
        .all()
    )
    return [
        DriverStatusResponse(
            hostname=h.hostname,
            driver_version=h.driver_version,
            cuda_version=h.cuda_version,
            machine_type=h.machine_type,
            reboot_required=h.reboot_required or False,
        )
        for h in hosts
    ]


@router.post("/upgrade")
async def upgrade_drivers(
    payload: DriverUpgradeRequest,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if payload.upgrade_mode not in ("standard", "major"):
        raise HTTPException(status_code=400, detail=f"Invalid upgrade mode: {payload.upgrade_mode}")
    if payload.upgrade_mode == "major":
        if not payload.target_driver_version or not payload.target_driver_version.isdigit():
            raise HTTPException(status_code=400, detail="Major upgrades require a numeric target driver version")

    invalid = (
        db.query(Host.hostname)
        .filter(
            Host.hostname.in_(payload.hosts),
            or_(
                Host.machine_type.is_(None),
                ~Host.machine_type.in_(GPU_MACHINE_TYPES),
            ),
        )
        .all()
    )
    if invalid:
        names = [host.hostname for host in invalid]
        raise HTTPException(
            status_code=400,
            detail=f"NVIDIA driver management is not supported on: {', '.join(names)}",
        )

    extra_vars = {"upgrade_mode": payload.upgrade_mode}
    if payload.target_driver_version:
        extra_vars["target_driver_version"] = payload.target_driver_version

    detail = f"Driver {payload.upgrade_mode} upgrade started on {', '.join(payload.hosts)}"
    if payload.target_driver_version:
        detail += f" (target: {payload.target_driver_version})"

    job_id = await run_playbook(
        db=db,
        playbook="driver_upgrade.yml",
        hosts=payload.hosts,
        all_hosts=False,
        extra_vars=extra_vars,
        triggered_by=user,
    )
    return {"job_id": job_id, "detail": detail}
