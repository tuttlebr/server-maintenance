from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.auth import get_current_user
from backend.capabilities import FABRIC_MANAGER_MACHINE_TYPES
from backend.database import get_db
from backend.models import Host
from backend.schemas import FabricManagerActionRequest
from backend.services.ansible_runner import run_playbook

router = APIRouter(prefix="/api/v1/networking", tags=["networking"])


@router.get("/status")
def get_networking_status(
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    hosts = db.query(Host).order_by(Host.hostname).all()
    return [
        {
            "hostname": h.hostname,
            "machine_type": h.machine_type,
            "nic_type": h.nic_type,
            "nic_speed": h.nic_speed,
            "fabric_manager_status": h.fabric_manager_status,
        }
        for h in hosts
    ]


@router.post("/fabric-manager/{action}")
async def manage_fabric_manager(
    action: str,
    payload: FabricManagerActionRequest | None = None,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if action not in ("status", "started", "stopped", "restarted"):
        raise HTTPException(status_code=400, detail=f"Invalid action: {action}")

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
                detail=f"Fabric Manager not supported on: {', '.join(names)}. Only dgx_workstation hosts have NVSwitch.",
            )

    extra_vars = {"fabric_action": action}

    job_id = await run_playbook(
        db=db,
        playbook="fabric_manager.yml",
        hosts=hosts,
        all_hosts=all_hosts,
        extra_vars=extra_vars,
        triggered_by=user,
    )
    return {"job_id": job_id, "detail": f"Fabric manager {action}"}
