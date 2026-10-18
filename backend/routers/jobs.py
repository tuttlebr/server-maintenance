import asyncio
import codecs
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, defer

from backend.auth import get_current_user
from backend.database import SessionLocal, get_db
from backend.models import Job
from backend.schemas import JobResponse, JobSummaryResponse
from backend.services.ansible_runner import cancel_job, get_log_path
from backend.services.execution_state import TERMINAL_STATUSES, release_devices
from backend.services.job_results import get_job_results

router = APIRouter(prefix="/api/v2/jobs", tags=["activity"])


def _summary_query(db):
    return db.query(Job).options(defer(Job.output_log), defer(Job.extra_vars))


@router.get("", response_model=list[JobSummaryResponse])
@router.get("/", response_model=list[JobSummaryResponse], include_in_schema=False)
def list_jobs(
    status: str | None = None,
    playbook: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    query = _summary_query(db)
    if status == "active":
        query = query.filter(Job.status.in_(("pending", "running", "cancelling")))
    elif status == "adverse":
        query = query.filter(Job.status.in_(("failed", "partial", "recovery_required")))
    elif status:
        query = query.filter(Job.status == status)
    if playbook:
        query = query.filter(Job.playbook == playbook)
    return query.order_by(Job.created_at.desc(), Job.id.desc()).offset(offset).limit(limit).all()


@router.get("/summary")
def job_summary(db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    return {"active_count": db.query(Job).filter(Job.status.in_(("pending", "running", "cancelling"))).count()}


@router.get("/overview")
def job_overview(db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    def rows(status=None, limit=50):
        return [
            JobSummaryResponse.model_validate(job)
            for job in list_jobs(status=status, limit=limit, offset=0, db=db, user=user,)
        ]

    return {
        **job_summary(db, user),
        "recent": rows(),
        "active": rows("active", 200),
        "adverse": rows("adverse", 15),
    }


@router.get("/{job_id}", response_model=JobResponse)
def get_job(
    job_id: str,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    job = db.query(Job).filter(Job.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    response = JobResponse.model_validate(job)
    return response.model_copy(update={"result_artifacts": get_job_results(job.job_id)})


@router.get("/{job_id}/progress", response_model=JobSummaryResponse)
def get_job_progress(
    job_id: str, db: Session = Depends(get_db), user: str = Depends(get_current_user),
):
    job = _summary_query(db).filter(Job.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return job


@router.post("/{job_id}/cancel")
async def cancel_job_output(
    job_id: str,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    job = db.query(Job).filter(Job.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    if job.status not in ("pending", "running"):
        raise HTTPException(status_code=400, detail=f"Job {job_id} is not running")
    if job.playbook.startswith("reachy.") or (job.status == "running" and job.execution_kind != "read_only"):
        raise HTTPException(
            status_code=400,
            detail="A running change cannot be safely cancelled. Monitor completion; interrupted changes trigger automatic health checks before the next install or cleanup.",
        )
    if job.status == "pending":
        release_devices(db, job_id)
        job.finished_at = datetime.now(timezone.utc)
        job.phase = "cancelled"
        job.outcomes_json = json.dumps([{"hostname":name, "status":"cancelled"} for name in (job.target_hosts or "").split(",") if name])
    cancel_job(job_id)
    job.status = "cancelled" if job.status == "pending" else "cancelling"
    job.error_summary = f"Cancellation requested by {user}"
    db.commit()
    return {"detail": f"Cancellation requested for {job_id}"}


@router.get("/{job_id}/stream")
async def stream_job_output(
    job_id: str, user: str = Depends(get_current_user),
):
    """Stream job output as Server-Sent Events. Auth via Authorization: Bearer header
    (frontend uses fetch streaming so headers are available)."""
    def read_status():
        # A stream must not retain a request-scoped DB connection while idle.
        with SessionLocal() as db:
            return db.query(Job.status).filter(Job.job_id == job_id).scalar()

    if await asyncio.to_thread(read_status) is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    log_path = get_log_path(job_id)

    def read_output(pos):
        if not log_path.exists():
            return b"", pos
        with log_path.open("rb") as handle:
            handle.seek(pos)
            return handle.read(64 * 1024), handle.tell()

    async def event_stream():
        pos = 0
        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        pending = ""
        while True:
            job_status = await asyncio.to_thread(read_status) or "failed"
            new_content, pos = await asyncio.to_thread(read_output, pos)
            if new_content:
                pending += decoder.decode(new_content)
                lines = pending.split("\n")
                pending = lines.pop()
                if lines:
                    yield "".join(f"data: {line.rstrip(chr(13))}\n" for line in lines) + "\n"
                # Drain the rest before signalling completion, without a poll delay.
                continue

            # If job is done, send final event and stop
            if job_status in TERMINAL_STATUSES:
                pending += decoder.decode(b"", final=True)
                if pending:
                    yield f"data: {pending}\n\n"
                yield f"event: done\ndata: {job_status}\n\n"
                break

            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no",},
    )
