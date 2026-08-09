from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from backend.auth import get_current_user
from backend.config import settings
from backend.database import get_db
from backend.models import ContextDocument, Device
from backend.schemas import ContextDocumentResponse, ContextStatusResponse
from backend.services import context_manager, docs_indexer

router = APIRouter(prefix="/api/v2/context", tags=["context"])


@router.get("/status", response_model=ContextStatusResponse)
def context_status(db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    index = docs_indexer.get_status()
    return ContextStatusResponse(
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
        for document in db.query(ContextDocument).order_by(ContextDocument.created_at.desc()).all()
    ]


@router.post("/documents", response_model=ContextDocumentResponse, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    title: str | None = Form(default=None, max_length=200),
    device_id: int | None = Form(default=None),
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    filename = file.filename or "document.txt"
    content = await file.read(settings.context_upload_max_bytes + 1)
    try:
        document = context_manager.create_document(
            db,
            filename=filename,
            content_bytes=content,
            title=title,
            device_id=device_id,
            uploaded_by=user,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
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
