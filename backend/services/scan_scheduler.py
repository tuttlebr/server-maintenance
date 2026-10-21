"""Hourly, read-only discovery using the same reserved jobs as manual scans."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from backend.capabilities import OPERATION_BY_ID, SYSTEM_SCAN, operation_ineligibility
from backend.database import SessionLocal
from backend.models import Device, DeviceReservation, Job
from backend.services.ansible_runner import run_playbook
from backend.services.execution_state import ACTIVE_STATUSES

logger = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(hours=1)
POLL_SECONDS = 60
TRIGGERED_BY = "Automatic hourly scan"


async def enqueue_due_scan(*, now: datetime | None = None) -> str | None:
    """Scan idle devices with no accepted scan in the last hour, including failures.

    Job history keeps the cadence across restarts and counts manual scans too.
    Busy devices remain due so the next poll can pick them up without delaying
    the rest of the fleet. Durable reservations also guard against manual work.
    """
    now = now or datetime.now(timezone.utc)
    operation = OPERATION_BY_ID[SYSTEM_SCAN]
    with SessionLocal() as db:
        if db.query(Job.job_id).filter(
            Job.triggered_by == TRIGGERED_BY,
            Job.status.in_(ACTIVE_STATUSES),
        ).first():
            return None

        recent_targets = {
            name
            for (targets,) in db.query(Job.target_hosts).filter(
                Job.playbook == operation.playbook,
                Job.created_at > now - SCAN_INTERVAL,
            )
            for name in (targets or "").split(",")
        }
        idle = db.query(Device).outerjoin(DeviceReservation).filter(
            DeviceReservation.device_id.is_(None),
        ).order_by(Device.hostname).all()
        targets = [
            device.hostname for device in idle
            if device.hostname not in recent_targets
            and operation_ineligibility(device, operation) is None
        ]
        if not targets:
            return None

        job_id = await run_playbook(
            db=db, playbook=operation.playbook, hosts=targets, triggered_by=TRIGGERED_BY,
        )
        logger.info("Automatic scan %s queued for %d devices", job_id, len(targets))
        return job_id


async def run_scan_scheduler():
    """Check immediately at startup, then pick up due devices once per minute."""
    logger.info("Automatic device scans enabled: every hour")
    while True:
        try:
            await enqueue_due_scan()
        except Exception:
            # A transient DB/queue failure must not disable future discovery.
            logger.exception("Could not schedule automatic scan; retrying in %s seconds", POLL_SECONDS)
        await asyncio.sleep(POLL_SECONDS)
