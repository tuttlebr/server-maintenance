"""Bounded async upload workers, independent of HTTP request lifetimes."""

import asyncio
from dataclasses import dataclass
import logging
from pathlib import Path
import tempfile
import threading

from backend.database import SessionLocal
from backend.services import context_manager
from backend.services.document_parser import PARSER_EXTENSIONS, ParserUnavailable, parse_document_async, run_blocking
from backend.services.upload_progress import uploads

logger = logging.getLogger(__name__)
_SAVE_LOCK = threading.Lock()


@dataclass
class Work:
    upload_id: str
    owner: str
    path: Path
    filename: str
    title: str | None
    device_id: int | None


class DocumentUploads:
    def __init__(self, progress=uploads, session_factory=SessionLocal, *, workers=2, capacity=6):
        self.progress = progress
        self.session_factory = session_factory
        self.worker_count = workers
        self.capacity = capacity
        self._workers = []
        self._pending = 0
        self._closing = True
        self._directory = None

    async def start(self):
        if self._workers:
            return
        self._directory = tempfile.TemporaryDirectory(prefix="fleet-document-uploads-")
        self._queue = asyncio.Queue(maxsize=self.capacity)
        self._closing = False
        self._workers = [asyncio.create_task(self._worker(), name=f"document-upload-{n}") for n in range(self.worker_count)]

    async def submit(self, upload_id, owner, *, content, filename, title, device_id):
        if self._closing or self._pending >= self.capacity:
            raise ParserUnavailable("Document upload queue is full or unavailable. Try again shortly.")
        self.progress.claim(upload_id, owner)
        self._pending += 1
        path = Path(self._directory.name) / upload_id
        try:
            await run_blocking(path.write_bytes, content)
            if self._closing:
                raise ParserUnavailable("Document processing is shutting down. Retry the upload shortly.")
            self.progress.update(upload_id, "queued")
            self._queue.put_nowait(Work(upload_id, owner, path, filename, title, device_id))
        except BaseException:
            self._pending -= 1
            self.progress.update(upload_id, "failed", error="The upload was not queued. Retry the upload.")
            await run_blocking(path.unlink, missing_ok=True)
            raise

    def _validate(self, work, content):
        with self.session_factory() as db:
            context_manager.validate_upload(db, filename=work.filename, content_bytes=content, device_id=work.device_id)

    def _save(self, work, content, parsed):
        # Each job owns its session. Never keep a request session or database
        # transaction open while waiting for the model. Recheck duplicates here.
        with _SAVE_LOCK, self.session_factory() as db:
            document = context_manager.create_document(
                db, filename=work.filename, content_bytes=content, title=work.title,
                device_id=work.device_id, uploaded_by=work.owner, parsed_content=parsed,
            )
            # Record success in this thread even if shutdown cancelled its await.
            self.progress.update(work.upload_id, "complete", document_id=document.id)

    async def _process(self, work):
        content = await run_blocking(work.path.read_bytes)
        self.progress.update(work.upload_id, "validating")
        await run_blocking(self._validate, work, content)
        parsed = None
        extension = Path(work.filename).suffix.lower()
        if extension in PARSER_EXTENSIONS:
            parsed = await parse_document_async(content, extension,
                lambda phase, done, total: self.progress.update(work.upload_id, phase, done, total))
        self.progress.update(work.upload_id, "saving")
        await run_blocking(self._save, work, content, parsed)

    async def _worker(self):
        while True:
            work = await self._queue.get()
            try:
                await self._process(work)
            except asyncio.CancelledError:
                if self.progress.get(work.upload_id, work.owner)["phase"] != "complete":
                    self.progress.update(work.upload_id, "failed", error="Document processing stopped during server shutdown. Retry the upload.")
                raise
            except (LookupError, FileExistsError, ValueError, ParserUnavailable) as exc:
                self.progress.update(work.upload_id, "failed", error=str(exc))
            except Exception as exc:
                logger.warning("Background document upload failed (%s)", type(exc).__name__)
                self.progress.update(work.upload_id, "failed", error="Document processing failed. Check uploaded documents before retrying.")
            finally:
                try:
                    await run_blocking(work.path.unlink, missing_ok=True)
                except OSError:
                    logger.warning("Could not remove temporary upload; shutdown will retry cleanup")
                finally:
                    self._pending -= 1
                    self._queue.task_done()

    async def shutdown(self):
        self._closing = True
        for task in self._workers:
            task.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers = []
        if self._directory is not None:
            while not self._queue.empty():
                work = self._queue.get_nowait()
                self.progress.update(work.upload_id, "failed", error="Document processing stopped during server shutdown. Retry the upload.")
                self._pending -= 1
                self._queue.task_done()
            await run_blocking(self._directory.cleanup)
            self._directory = None


document_uploads = DocumentUploads()
