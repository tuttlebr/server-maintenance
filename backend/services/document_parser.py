"""Optional Nemotron page parsing before uploaded documents enter the text index."""

import asyncio
import base64
import io
import logging
import re
import threading
import time
import warnings

import httpx
from PIL import Image, ImageOps, UnidentifiedImageError
import pypdfium2 as pdfium

from backend.config import settings
from backend.services.upload_progress import ProgressCallback

PARSER_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}
MAX_IMAGE_PIXELS = 25_000_000
# PDFium is not thread-safe, including across separate document instances.
_PDF_LOCK = threading.Lock()
_PARSE_SLOTS = threading.BoundedSemaphore(2)
TASK_PROMPT = "</s><s><predict_bbox><predict_classes><output_markdown><predict_text_in_pic>"
logger = logging.getLogger(__name__)


class ParserUnavailable(RuntimeError):
    """A configured parser failed; no document should be saved."""


def parser_enabled() -> bool:
    return bool(settings.parser_base_url.strip())


def _png(image: Image.Image) -> bytes:
    image = ImageOps.exif_transpose(image)
    image.thumbnail((1664, 2048))
    rgba = image.convert("RGBA")
    rgb = Image.new("RGB", rgba.size, "white")
    rgb.paste(rgba, mask=rgba.getchannel("A"))
    output = io.BytesIO()
    rgb.save(output, format="PNG")
    return output.getvalue()


def iter_pages(content: bytes, extension: str, progress: ProgressCallback | None = None):
    """Render one page at a time; never hold PDFium's lock across a yield."""
    if extension != ".pdf":
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(content)) as image:
                    if image.format not in {"PNG", "JPEG"}:
                        raise ValueError("Only PNG and JPEG page images are supported")
                    if image.width * image.height > MAX_IMAGE_PIXELS:
                        raise ValueError("Page images may not exceed 25 million pixels")
                    page = _png(image)
            if progress:
                progress("rendering", 1, 1)
            yield 1, page
            return
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
            raise ValueError("The page image is invalid or too large") from exc

    document = None
    try:
        with _PDF_LOCK:
            document = pdfium.PdfDocument(content)
            total = len(document)
        if not 0 < total <= settings.parser_max_pages:
            raise ValueError(f"PDFs must contain 1–{settings.parser_max_pages} pages")
        if progress:
            progress("rendering", 0, total)
        for index in range(total):
            with _PDF_LOCK:
                page = document[index]
                try:
                    width, height = page.get_size()
                    if width <= 0 or height <= 0:
                        raise ValueError("PDF contains an invalid page size")
                    bitmap = page.render(scale=min(1664 / width, 2048 / height, 2))
                    try:
                        encoded = _png(bitmap.to_pil())
                    finally:
                        bitmap.close()
                finally:
                    page.close()
            if progress:
                progress("rendering", index + 1, total)
            yield total, encoded
    except pdfium.PdfiumError as exc:
        raise ValueError("The PDF is invalid or password-protected") from exc
    finally:
        if document is not None:
            with _PDF_LOCK:
                document.close()


def render_pages(content: bytes, extension: str, progress: ProgressCallback | None = None) -> list[bytes]:
    """Compatibility helper for callers that explicitly need all rendered pages."""
    return [page for _, page in iter_pages(content, extension, progress)]


async def run_blocking(function, *args, **kwargs):
    """Offload CPU/disk/DB work and finish it before cancellation cleans resources."""
    task = asyncio.create_task(asyncio.to_thread(function, *args, **kwargs))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError as cancelled:
        try:
            await task
        except Exception:
            # Preserve cancellation so a shutdown cannot turn into another job.
            pass
        raise cancelled


def readable_content(raw: str) -> str:
    """Remove layout/control tokens while retaining text, Markdown, and table markup.

    Keep native LaTeX/HTML tables intact instead of flattening cells or spans.
    """
    raw = re.sub(r"<class_[^>]+>", "\n\n", raw)
    raw = re.sub(r"<(?:x_|y_)[^>]+>", "", raw)
    raw = re.sub(r"</?s>|<pad>|<tbc>|<predict_[^>]+>|<output_markdown>", "", raw)
    return raw.strip()


async def _request_page(page: bytes, remaining: float, client: httpx.AsyncClient) -> dict:
    base = settings.parser_base_url.strip().rstrip("/")
    # HTTPX's timeout applies separately to socket operations. Bound the entire
    # page request as well, including a slowly streaming response body.
    async with asyncio.timeout(remaining):
        if settings.parser_api_format == "nim":
            response = await client.post(base + "/parse", files={"document": ("page.png", page, "image/png")}, timeout=remaining)
        elif settings.parser_api_format == "nv-ingest":
            response = await client.post(base + "/parse", timeout=remaining, json={
                "image": base64.b64encode(page).decode("ascii"),
            })
        else:
            response = await client.post(base + "/chat/completions", timeout=remaining, json={
                "model": settings.parser_model,
                "messages": [{"role": "user", "content": [
                    {"type": "text", "text": TASK_PROMPT},
                    {"type": "image_url", "image_url": {
                        "url": "data:image/png;base64," + base64.b64encode(page).decode("ascii"),
                    }},
                ]}],
            })
        response.raise_for_status()
        return response.json()


async def parse_document_async(content: bytes, extension: str, progress: ProgressCallback | None = None) -> str:
    if not parser_enabled():
        raise ValueError("PDF and image uploads require PARSER_BASE_URL to be configured")
    if not _PARSE_SLOTS.acquire(blocking=False):
        raise ParserUnavailable("Document parser is busy. Try the upload again shortly.")
    pages = iter_pages(content, extension, progress)
    try:
        deadline = time.monotonic() + settings.parser_timeout_seconds
        headers = {"Authorization": f"Bearer {settings.parser_api_key}"} if settings.parser_api_key else {}
        parsed, size = [], 0
        if progress:
            progress("rendering", 0, 0)
        async with httpx.AsyncClient(headers=headers, follow_redirects=False) as client:
            while True:
                if time.monotonic() >= deadline:
                    raise ParserUnavailable("Document parsing timed out. Upload fewer pages or increase the parsing budget.")
                rendered = await run_blocking(next, pages, None)
                if rendered is None:
                    break
                total, page = rendered
                number = len(parsed) + 1
                if progress and number == 1:
                    progress("parsing", 0, total)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ParserUnavailable("Document parsing timed out. Upload fewer pages or increase the parsing budget.")
                try:
                    payload = await _request_page(page, remaining, client)
                    if settings.parser_api_format == "nim":
                        raw, finish = payload["content"], payload["finish_reason"]
                    elif settings.parser_api_format == "nv-ingest":
                        # The local nv-ingest adapter returns Markdown and rejects
                        # truncated generation with HTTP 422 instead of finish_reason.
                        raw, finish = payload["markdown"], payload.get("finish_reason", "stop")
                    else:
                        choice = payload["choices"][0]
                        raw, finish = choice["message"]["content"], choice["finish_reason"]
                    if finish != "stop" or not isinstance(raw, str):
                        raise ValueError("Incomplete parser response")
                    text = readable_content(raw)
                    if not text:
                        raise ValueError("Empty parser response")
                except (TimeoutError, httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as exc:
                    # Avoid leaking image data, credentials, or remote error bodies.
                    if isinstance(exc, httpx.HTTPStatusError):
                        reason = f"Parser returned HTTP {exc.response.status_code}"
                    elif isinstance(exc, (TimeoutError, httpx.TimeoutException)):
                        reason = "Parser request timed out"
                    elif isinstance(exc, httpx.RequestError):
                        reason = "Parser connection failed"
                    else:
                        reason = "Parser returned invalid, empty, or incomplete text"
                    logger.warning("%s for page %d (format=%s, error=%s)",
                                   reason, number, settings.parser_api_format, type(exc).__name__)
                    raise ParserUnavailable(f"{reason} for page {number}. No document was saved.") from exc
                part = f"## Page {number}\n\n{text}"
                size += len(part.encode("utf-8"))
                if size > settings.context_upload_max_bytes:
                    raise ValueError("Parsed text exceeds the upload size limit")
                parsed.append(part)
                if progress:
                    progress("parsing", number, total)
                # Drop image references before rendering the next page.
                del page, rendered
                if number == total:
                    break
        return "\n\n".join(parsed)
    finally:
        try:
            await run_blocking(pages.close)
        finally:
            _PARSE_SLOTS.release()


def parse_document(content: bytes, extension: str, progress: ProgressCallback | None = None) -> str:
    """Synchronous compatibility entry point; one event loop/client per document."""
    return asyncio.run(parse_document_async(content, extension, progress))
