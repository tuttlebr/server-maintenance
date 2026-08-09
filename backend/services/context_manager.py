"""Persistent user context and generated device context for Fleet Help."""

from __future__ import annotations

import hashlib
import re
import shutil
from pathlib import Path

from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import SessionLocal
from backend.models import ContextDocument, Device

ALLOWED_EXTENSIONS = {".md", ".markdown", ".txt"}


def create_document(
    db: Session,
    *,
    filename: str,
    content_bytes: bytes,
    title: str | None,
    device_id: int | None,
    uploaded_by: str,
) -> ContextDocument:
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError("Only .txt, .md, and .markdown files are supported")
    if len(content_bytes) > settings.context_upload_max_bytes:
        raise ValueError(f"Files may not exceed {settings.context_upload_max_bytes // (1024 * 1024)} MB")
    try:
        content = content_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("The file must contain UTF-8 text") from exc
    if len(content.strip()) < 20:
        raise ValueError("The document does not contain enough text to index")
    if device_id is not None and not db.query(Device).filter(Device.id == device_id).first():
        raise LookupError("Device not found")

    digest = hashlib.sha256(content_bytes).hexdigest()
    existing = (
        db.query(ContextDocument)
        .filter(ContextDocument.sha256 == digest, ContextDocument.device_id == device_id)
        .first()
    )
    if existing:
        raise FileExistsError("This document is already uploaded for that device")

    resolved_title = " ".join(
        (title or _title_from_content(content) or Path(filename).stem).replace("\x00", "").split()
    )[:200]
    if not resolved_title:
        raise ValueError("A document title could not be determined")
    normalized_content_type = "text/markdown" if extension in {".md", ".markdown"} else "text/plain"
    document = ContextDocument(
        title=resolved_title,
        original_filename=Path(filename).name[:255],
        content_type=normalized_content_type,
        content=content,
        size_bytes=len(content_bytes),
        sha256=digest,
        device_id=device_id,
        uploaded_by=uploaded_by,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def prepare_index_sources(destination: Path) -> int:
    """Materialize built-in docs, uploads, and current device metadata as Markdown."""
    destination.mkdir(parents=True, exist_ok=True)
    count = 0
    if settings.docs_dir.exists():
        for source in sorted(settings.docs_dir.glob("*.md")):
            shutil.copy2(source, destination / f"builtin-{source.name}")
            count += 1

    db = SessionLocal()
    try:
        devices = db.query(Device).order_by(Device.hostname).all()
        device_map = {device.id: device for device in devices}
        for document in db.query(ContextDocument).order_by(ContextDocument.id).all():
            rendered = _render_uploaded_document(document, device_map.get(document.device_id))
            (destination / f"upload-{document.id}.md").write_text(rendered, encoding="utf-8")
            count += 1

        device_context = render_device_context(devices)
        if device_context:
            (destination / "fleet-device-context.md").write_text(device_context, encoding="utf-8")
            count += 1
    finally:
        db.close()
    return count


def render_device_context(devices: list[Device] | None = None) -> str:
    owns_session = devices is None
    db = SessionLocal() if owns_session else None
    try:
        if devices is None:
            devices = db.query(Device).order_by(Device.hostname).all()  # type: ignore[union-attr]
        if not devices:
            return ""
        lines = [
            "# Fleet Device Context",
            "",
            "Current discovered identity and operator-provided attributes for managed devices.",
        ]
        for device in devices:
            lines.extend(["", f"## {device.name}"])
            _add_field(lines, "Inventory name", device.hostname)
            _add_field(lines, "Endpoint", device.endpoint or device.ip_address)
            _add_field(lines, "Kind", device.kind)
            _add_field(lines, "System vendor", device.vendor)
            _add_field(lines, "System model", device.model)
            _add_field(lines, "Architecture", device.architecture)
            _add_field(lines, "Operating system", device.os_version or device.os_family)
            _add_field(lines, "GPU", device.gpu_model)
            _add_field(lines, "Memory", f"{device.memory_gb} GB" if device.memory_gb else None)
            facts = device.facts
            for label, path in (
                ("Motherboard vendor", ("motherboard", "vendor")),
                ("Motherboard model", ("motherboard", "model")),
                ("Motherboard version", ("motherboard", "version")),
                ("BIOS vendor", ("bios", "vendor")),
                ("BIOS version", ("bios", "version")),
                ("BIOS date", ("bios", "date")),
                ("CPU model", ("cpu", "model")),
                ("Kernel", ("kernel",)),
                ("Virtualization", ("virtualization",)),
            ):
                _add_field(lines, label, _nested(facts, path))
            if device.capabilities:
                _add_field(lines, "Capabilities", ", ".join(device.capabilities))
            if device.annotations:
                lines.extend(["", "### Manual attributes"])
                for key, value in sorted(device.annotations.items()):
                    _add_field(lines, key, value)
        return "\n".join(lines).strip() + "\n"
    finally:
        if db is not None:
            db.close()


def get_relevant_context(query: str, max_chars: int = 30000) -> str:
    """Keyword fallback for direct-LLM mode when the Milvus agent isn't active."""
    query_terms = set(re.findall(r"\w+", query.lower()))
    db = SessionLocal()
    try:
        devices = db.query(Device).order_by(Device.hostname).all()
        device_map = {device.id: device for device in devices}
        candidates: list[tuple[int, str]] = []
        live_context = render_device_context(devices)
        if live_context:
            score = len(query_terms & set(re.findall(r"\w+", live_context.lower())))
            candidates.append((max(score, 1), live_context))
        for document in db.query(ContextDocument).all():
            rendered = _render_uploaded_document(document, device_map.get(document.device_id))
            score = len(query_terms & set(re.findall(r"\w+", rendered.lower())))
            if score:
                candidates.append((score, rendered))
    finally:
        db.close()

    candidates.sort(key=lambda item: item[0], reverse=True)
    selected: list[str] = []
    total = 0
    for _score, text in candidates:
        remaining = max_chars - total
        if remaining <= 0:
            break
        selected.append(text[:remaining])
        total += min(len(text), remaining)
    return "\n\n---\n\n".join(selected)


def document_to_dict(document: ContextDocument, device: Device | None = None) -> dict:
    return {
        "id": document.id,
        "title": document.title,
        "original_filename": document.original_filename,
        "content_type": document.content_type,
        "size_bytes": document.size_bytes,
        "sha256": document.sha256,
        "device_id": document.device_id,
        "device_name": device.name if device else None,
        "uploaded_by": document.uploaded_by,
        "created_at": document.created_at,
    }


def _render_uploaded_document(document: ContextDocument, device: Device | None) -> str:
    indexed_title = f"{document.title} for device {device.name}" if device else document.title
    lines = [f"# {indexed_title}", "", f"Uploaded file: {document.original_filename}"]
    if device:
        lines.extend(
            [
                f"Associated device: {device.name}",
                f"Device inventory name: {device.hostname}",
            ]
        )
        if device.vendor or device.model:
            lines.append(f"Device system: {' '.join(filter(None, [device.vendor, device.model]))}")
        for key, value in sorted(device.annotations.items()):
            _add_field(lines, f"Device {key}", value)
    lines.extend(["", "## Document content", "", document.content.strip(), ""])
    return "\n".join(lines)


def _title_from_content(content: str) -> str | None:
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip() or None
    return None


def _add_field(lines: list[str], label: str, value) -> None:
    if value is None or value == "":
        return
    clean = " ".join(str(value).replace("\x00", "").split())
    if clean:
        lines.append(f"- {label}: {clean[:1000]}")


def _nested(value: dict, path: tuple[str, ...]):
    current = value
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current
