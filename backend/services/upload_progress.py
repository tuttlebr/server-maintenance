"""Bounded, owner-scoped upload progress for the single-process web service.

Progress is transient: a restart loses status, but never changes saved documents.
No filenames, document text, or credentials are kept here.
"""

from collections.abc import Callable
from dataclasses import dataclass
import threading
import time
from uuid import uuid4

ProgressCallback = Callable[[str, int, int], None]
RETENTION_SECONDS = 900
MAX_UPLOADS = 256


@dataclass
class Upload:
    owner: str
    started: float
    updated: float
    phase: str = "uploading"
    completed: int = 0
    total: int = 0
    last_page_completed: float | None = None
    error: str | None = None
    document_id: int | None = None


class UploadProgress:
    def __init__(self):
        self._lock = threading.Lock()
        self._uploads: dict[str, Upload] = {}

    def _prune(self, now: float):
        # An active model call can outlast the retention period. Keep its status
        # until the request's configured deadline ends it.
        for key, item in list(self._uploads.items()):
            if item.phase in {"uploading", "complete", "failed"} and now - item.updated > RETENTION_SECONDS:
                del self._uploads[key]

    def _owned(self, upload_id: str, owner: str) -> Upload:
        item = self._uploads.get(upload_id)
        if item is None or item.owner != owner:
            raise LookupError("Upload status expired or is unavailable. Check uploaded documents before retrying.")
        return item

    def create(self, owner: str) -> str:
        with self._lock:
            now = time.monotonic()
            self._prune(now)
            if len(self._uploads) >= MAX_UPLOADS:
                finished = [key for key, item in self._uploads.items() if item.phase in {"complete", "failed"}]
                if not finished:
                    raise ValueError("Too many pending uploads. Try again later.")
                del self._uploads[finished[0]]
            upload_id = str(uuid4())
            self._uploads[upload_id] = Upload(owner, now, now)
            return upload_id

    def claim(self, upload_id: str, owner: str):
        with self._lock:
            self._prune(time.monotonic())
            item = self._owned(upload_id, owner)
            if item.phase != "uploading":
                raise ValueError("This upload ID has already been used.")
            item.phase = "validating"
            item.updated = time.monotonic()

    def update(self, upload_id: str, phase: str, completed: int = 0, total: int = 0,
               *, error: str | None = None, document_id: int | None = None):
        with self._lock:
            item = self._uploads[upload_id]
            now = time.monotonic()
            if phase == "parsing" and completed > item.completed:
                item.last_page_completed = now
            item.phase, item.completed, item.total = phase, completed, total
            item.error, item.document_id, item.updated = error, document_id, now

    def get(self, upload_id: str, owner: str) -> dict:
        with self._lock:
            now = time.monotonic()
            self._prune(now)
            item = self._owned(upload_id, owner)
            end = item.updated if item.phase in {"complete", "failed"} else now
            return {
                "upload_id": upload_id, "phase": item.phase,
                "completed": item.completed, "total": item.total,
                "elapsed_seconds": round(end - item.started, 1),
                "seconds_since_last_page": round(end - item.last_page_completed, 1) if item.last_page_completed is not None else None,
                "error": item.error, "document_id": item.document_id,
            }


uploads = UploadProgress()
