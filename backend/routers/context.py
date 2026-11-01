from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session, defer
from starlette.concurrency import run_in_threadpool

from backend.auth import get_current_user
from backend.config import settings
from backend.database import get_db
from backend.models import ContextDocument, Device
from backend.schemas import ContextDocumentResponse, ContextStatusResponse
from backend.services import context_manager, docs_indexer
from backend.services.document_parser import ParserUnavailable, parser_enabled
from backend.services.upload_progress import uploads

router = APIRouter(prefix="/api/v2/context", tags=["context"])


@router.get("/status", response_model=ContextStatusResponse)
def context_status(db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    index = docs_indexer.get_status()
    return ContextStatusResponse(
        parser_enabled=parser_enabled(),
        upload_max_bytes=settings.context_upload_max_bytes,
        parser_max_pages=settings.parser_max_pages,
        parser_timeout_seconds=settings.parser_timeout_seconds,
        record_count=index.get("last_count"),
        document_count=db.query(ContextDocument).count(),
        annotated_device_count=sum(bool(device.annotations) for device in db.query(Device).all()),
        running=bool(index.get("running")),
        phase=index.get("phase") or "idle",
        message=index.get("message") or "",
        progress=index.get("progress") or 0,
        total=index.get("total") or 0,
        started_at=index.get("started_at"),
        completed_at=index.get("completed_at"),
        last_indexed_at=index.get("last_indexed_at"),
        error=index.get("error"),
    )


@router.get("/documents", response_model=list[ContextDocumentResponse])
def list_documents(db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    devices = {device.id: device for device in db.query(Device).all()}
    return [
        context_manager.document_to_dict(document, devices.get(document.device_id))
        for document in db.query(ContextDocument).options(defer(ContextDocument.content)).order_by(ContextDocument.created_at.desc()).all()
    ]


@router.post("/uploads", status_code=201)
def start_upload(user: str = Depends(get_current_user)):
    try:
        return {"upload_id": uploads.create(user), "parser_timeout_seconds": settings.parser_timeout_seconds}
    except ValueError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc


@router.get("/uploads/{upload_id}")
def upload_status(upload_id: UUID, user: str = Depends(get_current_user)):
    try:
        return uploads.get(str(upload_id), user)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/documents", response_model=ContextDocumentResponse, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    title: str | None = Form(default=None, max_length=200),
    device_id: int | None = Form(default=None),
    upload_id: UUID | None = Form(default=None),
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    key = str(upload_id) if upload_id else None
    if key:
        try:
            uploads.claim(key, user)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    def report(phase: str, completed: int, total: int):
        if key:
            uploads.update(key, phase, completed, total)

    try:
        filename = file.filename or "document.txt"
        content = await file.read(settings.context_upload_max_bytes + 1)
        document = await run_in_threadpool(
            context_manager.create_document,
            db,
            filename=filename,
            content_bytes=content,
            title=title,
            device_id=device_id,
            uploaded_by=user,
            progress=report,
        )
    except (LookupError, FileExistsError, ValueError, ParserUnavailable) as exc:
        db.rollback()
        if key:
            uploads.update(key, "failed", error=str(exc))
        status = 404 if isinstance(exc, LookupError) else 409 if isinstance(exc, FileExistsError) else 422 if isinstance(exc, ValueError) else 502
        raise HTTPException(status_code=status, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        if key:
            uploads.update(key, "failed", error="Document processing failed. Check uploaded documents before retrying.")
        raise
    if key:
        uploads.update(key, "complete", document_id=document.id)
    device = db.query(Device).filter(Device.id == document.device_id).first() if document.device_id else None
    return context_manager.document_to_dict(document, device)


@router.delete("/documents/{document_id}")
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    document = db.query(ContextDocument).filter(ContextDocument.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Context document not found")
    title = document.title
    db.delete(document)
    db.commit()
    return {"detail": f"Removed {title}; re-index to remove its records from search"}


@router.post("/reindex")
def reindex_context(user: str = Depends(get_current_user)):
    if not docs_indexer.start_reindex():
        raise HTTPException(status_code=409, detail="A re-index is already in progress")
    return {"detail": "Context re-index started"}
