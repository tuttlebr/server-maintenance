import asyncio

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.auth import get_current_user
from backend.config import settings
from backend.database import SessionLocal, get_db
from backend.models import Job
from backend.schemas import JobResponse
from backend.services.ansible_runner import cancel_job, get_log_path
from backend.services.tokens import TokenError, decode_token

router = APIRouter(prefix="/api/v2/jobs", tags=["activity"])


@router.get("/", response_model=list[JobResponse])
def list_jobs(
    status: str | None = None,
    playbook: str | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    query = db.query(Job)
    if status:
        query = query.filter(Job.status == status)
    if playbook:
        query = query.filter(Job.playbook == playbook)
    return query.order_by(Job.created_at.desc()).offset(offset).limit(limit).all()


@router.get("/{job_id}", response_model=JobResponse)
def get_job(
    job_id: str,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    job = db.query(Job).filter(Job.job_id == job_id).first()
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
    if job.playbook in {"reachy.daemon.restart", "reachy.software.update"}:
        raise HTTPException(
            status_code=400,
            detail="This Reachy operation cannot be cancelled after the daemon accepts it",
        )
    cancel_job(job_id)
    job.status = "cancelled"
    job.error_summary = f"Cancellation requested by {user}"
    db.commit()
    return {"detail": f"Cancellation requested for {job_id}"}


@router.get("/{job_id}/stream")
async def stream_job_output(
    job_id: str,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """Stream job output as Server-Sent Events. Auth via Authorization: Bearer header
    (frontend uses fetch streaming so headers are available)."""
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(None, 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Token required")
    try:
        payload = decode_token(token, settings.secret_key)
        if not payload.get("sub"):
            raise HTTPException(status_code=401, detail="Invalid token")
    except TokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

    job = db.query(Job).filter(Job.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    log_path = get_log_path(job_id)

    async def event_stream():
        pos = 0
        while True:
            # Re-check job status from DB
            fresh_db = SessionLocal()
            try:
                current_job = fresh_db.query(Job).filter(Job.job_id == job_id).first()
                job_status = current_job.status if current_job else "failed"
            finally:
                fresh_db.close()

            # Read new content from log file
            if log_path.exists():
                with open(log_path, "r") as f:
                    f.seek(pos)
                    new_content = f.read()
                    pos = f.tell()

                if new_content:
                    # SSE format: each line prefixed with "data: ", blank line terminates event
                    for line in new_content.splitlines():
                        yield f"data: {line}\n"
                    yield "\n"

            # If job is done, send final event and stop
            if job_status in ("success", "failed", "cancelled"):
                yield f"event: done\ndata: {job_status}\n\n"
                break

            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
