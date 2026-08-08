"""On-demand documentation reindexer for the Fleet Help Milvus collection.

The Operations experience triggers this module through /api/v2/chat/reindex-docs.
Reindexing runs in a background thread and invokes the Rust crawler/ingester
that is built into the web Docker image at /usr/local/bin/fleet-doc-ingester.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path

from backend.config import settings

COLLECTION_NAME = "fleet_docs"
EMBED_BATCH_SIZE = 16
INSERT_BATCH_SIZE = 64

_PREPARED_RE = re.compile(r"Prepared (?P<count>\d+) Markdown chunk")
_EMBED_RE = re.compile(r"Embedding batch (?P<current>\d+)/(?P<total>\d+)")
_INSERT_RE = re.compile(r"Inserting Milvus batch (?P<current>\d+)/(?P<total>\d+)")
_INGESTED_RE = re.compile(r"Ingested (?P<count>\d+) chunk")

_state_lock = threading.Lock()
_state: dict = {
    "running": False,
    "phase": "idle",  # idle | loading | embedding | inserting | success | error
    "message": "",
    "progress": 0,
    "total": 0,
    "started_at": None,
    "completed_at": None,
    "last_count": None,
    "last_indexed_at": None,
    "error": None,
}


def get_status() -> dict:
    """Return a snapshot of the indexer state. Safe to call from any thread."""
    with _state_lock:
        snap = dict(_state)
    if not snap["running"] and snap["last_count"] is None:
        snap["last_count"] = _peek_count()
    return snap


def start_reindex() -> bool:
    """Kick off a reindex in a background thread. Returns False if already running."""
    with _state_lock:
        if _state["running"]:
            return False
        _state["running"] = True
    threading.Thread(target=_safe_run, daemon=True, name="docs-reindex").start()
    return True


def _safe_run() -> None:
    try:
        _run_reindex_inner()
    except Exception as e:
        _set(
            running=False,
            phase="error",
            error=f"Unexpected: {e}",
            completed_at=datetime.now(timezone.utc).isoformat(),
        )


def _set(**kwargs) -> None:
    with _state_lock:
        _state.update(kwargs)


def _peek_count() -> int | None:
    """Return current entity count from Milvus. None on connection/import errors."""
    try:
        from pymilvus import Collection, connections, utility
    except ImportError:
        return None

    try:
        _connect()
        if not utility.has_collection(COLLECTION_NAME):
            return 0
        coll = Collection(COLLECTION_NAME)
        try:
            coll.load()
            return int(coll.num_entities)
        except Exception:
            return None
    except Exception:
        return None


def _connect() -> None:
    from pymilvus import connections

    uri = settings.milvus_uri
    host = uri.replace("http://", "").replace("https://", "").split(":")[0]
    port_part = uri.replace("http://", "").replace("https://", "").split(":")
    port = port_part[-1] if len(port_part) > 1 else "19530"
    if not connections.has_connection("default"):
        connections.connect("default", host=host, port=port, timeout=2)


def _run_reindex_inner() -> None:
    started = datetime.now(timezone.utc)
    _set(
        running=True,
        phase="loading",
        message="Starting documentation crawler",
        progress=0,
        total=0,
        started_at=started.isoformat(),
        completed_at=None,
        error=None,
    )

    if not settings.docs_urls_file.exists():
        _fail(f"Docs URL file not found: {settings.docs_urls_file}")
        return

    if not _embedding_api_key_configured():
        _fail("Embedding API key is not configured; set EMBED_API_KEY or AI_HELPER_API_KEY")
        return

    settings.docs_markdown_dir.mkdir(parents=True, exist_ok=True)

    command = _ingester_command()
    if command is None:
        _fail(
            f"Rust ingester not found at {settings.docs_ingester_bin}. "
            "Rebuild the Docker image or run cargo build for local development."
        )
        return

    args = [
        *command,
        "--urls",
        str(settings.docs_urls_file),
        "--local-docs-dir",
        str(settings.docs_dir),
        "--markdown-dir",
        str(settings.docs_markdown_dir),
        "--collection",
        COLLECTION_NAME,
        "--milvus-uri",
        settings.milvus_uri,
        "--embed-batch-size",
        str(EMBED_BATCH_SIZE),
        "--insert-batch-size",
        str(INSERT_BATCH_SIZE),
    ]

    env = _ingester_env()
    cwd = _working_dir()
    _set(message="Crawling documentation links")

    try:
        proc = subprocess.Popen(
            args,
            cwd=str(cwd),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except Exception as e:
        _fail(f"Couldn't start Rust ingester: {e}")
        return

    total_chunks = 0
    recent_lines: list[str] = []

    assert proc.stdout is not None
    for raw_line in proc.stdout:
        line = raw_line.strip()
        if not line:
            continue
        recent_lines.append(line)
        recent_lines = recent_lines[-8:]
        total_chunks = _handle_ingester_line(line, total_chunks)

    return_code = proc.wait()
    if return_code != 0:
        details = "\n".join(recent_lines)
        _fail(f"Rust ingester exited with code {return_code}. {details}".strip())
        return

    count = _extract_count_from_lines(recent_lines) or _peek_count() or total_chunks
    completed = datetime.now(timezone.utc).isoformat()
    _set(
        running=False,
        phase="success",
        message=f"Indexed {count} sections",
        progress=count,
        total=count,
        last_count=count,
        last_indexed_at=completed,
        completed_at=completed,
        error=None,
    )


def _handle_ingester_line(line: str, total_chunks: int) -> int:
    if line.startswith("Crawling "):
        _set(phase="loading", message=line, progress=0, total=0)
        return total_chunks

    if line.startswith("Wrote "):
        _set(phase="loading", message=line)
        return total_chunks

    prepared = _PREPARED_RE.search(line)
    if prepared:
        total_chunks = int(prepared.group("count"))
        _set(phase="embedding", message=line, progress=0, total=total_chunks)
        return total_chunks

    embed = _EMBED_RE.search(line)
    if embed:
        current = int(embed.group("current"))
        total_batches = int(embed.group("total"))
        progress, total = _batch_progress(current, total_batches, EMBED_BATCH_SIZE, total_chunks)
        _set(phase="embedding", message=line, progress=progress, total=total)
        return total_chunks

    if line.startswith("Creating Milvus collection") or line.startswith("Dropping existing Milvus collection"):
        _set(phase="inserting", message=line, progress=0, total=total_chunks)
        return total_chunks

    insert = _INSERT_RE.search(line)
    if insert:
        current = int(insert.group("current"))
        total_batches = int(insert.group("total"))
        progress, total = _batch_progress(current, total_batches, INSERT_BATCH_SIZE, total_chunks)
        _set(phase="inserting", message=line, progress=progress, total=total)
        return total_chunks

    ingested = _INGESTED_RE.search(line)
    if ingested:
        count = int(ingested.group("count"))
        _set(phase="inserting", message=line, progress=count, total=count)
        return count

    _set(message=line)
    return total_chunks


def _batch_progress(current_batch: int, total_batches: int, batch_size: int, total_chunks: int) -> tuple[int, int]:
    if total_chunks > 0:
        return min(current_batch * batch_size, total_chunks), total_chunks
    return current_batch, total_batches


def _extract_count_from_lines(lines: list[str]) -> int | None:
    for line in reversed(lines):
        match = _INGESTED_RE.search(line)
        if match:
            return int(match.group("count"))
    return None


def _fail(message: str) -> None:
    _set(
        running=False,
        phase="error",
        error=message,
        message=message,
        completed_at=datetime.now(timezone.utc).isoformat(),
    )


def _embedding_api_key_configured() -> bool:
    return bool(
        settings.embed_api_key
        or settings.ai_helper_api_key
        or os.environ.get("EMBED_API_KEY")
        or os.environ.get("AI_HELPER_API_KEY")
    )


def _ingester_command() -> list[str] | None:
    configured = settings.docs_ingester_bin
    if configured.exists():
        return [str(configured)]

    cargo = shutil.which("cargo")
    manifest = _repo_root() / "tools" / "dgx-doc-ingester" / "Cargo.toml"
    if cargo and manifest.exists():
        return [cargo, "run", "--manifest-path", str(manifest), "--"]

    return None


def _ingester_env() -> dict[str, str]:
    env = os.environ.copy()
    env["MILVUS_URI"] = settings.milvus_uri
    env["EMBED_MODEL"] = settings.embed_model

    if settings.embed_dim:
        env["EMBED_DIM"] = str(settings.embed_dim)
    if settings.embed_api_key:
        env["EMBED_API_KEY"] = settings.embed_api_key
    if settings.embed_base_url:
        env["EMBED_BASE_URL"] = settings.embed_base_url
    if settings.ai_helper_api_key:
        env["AI_HELPER_API_KEY"] = settings.ai_helper_api_key
    if settings.ai_helper_base_url:
        env["AI_HELPER_BASE_URL"] = settings.ai_helper_base_url

    return env


def _working_dir() -> Path:
    root = _repo_root()
    if (root / "tools" / "dgx-doc-ingester").exists():
        return root
    return Path("/app")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]
