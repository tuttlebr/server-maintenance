"""Index completed Ansible job logs and a current fleet snapshot in Milvus.

The database remains the source of truth.  Milvus contains a derived, redacted
search index used by the NeMo Agent Toolkit chat workflow.  Writes are
idempotent so startup reconciliation can recover jobs missed while Milvus or
the embedding endpoint was unavailable.
"""

from __future__ import annotations

import json
import logging
import re
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone

from backend.config import settings
from backend.database import SessionLocal
from backend.models import Host, Job

logger = logging.getLogger(__name__)

COLLECTION_NAME = "fleet_job_logs"
COLLECTION_ALIAS = "fleet_job_logs_indexer"
SNAPSHOT_JOB_ID = "__fleet_snapshot__"
TERMINAL_STATUSES = ("success", "failed", "cancelled")
EMBED_BATCH_SIZE = 16
MAX_CHUNK_CHARS = 3_500
MAX_INDEXED_LOG_CHARS = 200_000
RECENT_JOB_COUNT = 20

_INDEX_LOCK = threading.Lock()
_RECONCILE_LOCK = threading.Lock()
_reconcile_thread: threading.Thread | None = None

_PRIVATE_KEY_RE = re.compile(
    r"-----BEGIN [^-\n]*PRIVATE KEY-----.*?-----END [^-\n]*PRIVATE KEY-----",
    re.IGNORECASE | re.DOTALL,
)
_BEARER_RE = re.compile(r'''(?i)(authorization["']?\s*[:=]\s*["']?bearer\s+)[^\s,"';}]+''')
_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)(\b(?:[\w-]*[_-])?(?:password|passwd|secret|token|api[_-]?key)\b[\"']?\s*[:=]\s*)"
    r'''("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|[^\s,;}]+)'''
)


@dataclass(frozen=True)
class IndexDocument:
    document_id: str
    source: str
    heading: str
    text: str
    job_id: str
    status: str
    finished_at: str


def ingest_completed_job(job_id: str) -> bool:
    """Index one terminal job and refresh the latest-per-host fleet snapshot.

    Returns False when indexing is not configured or the job is not terminal.
    Operational failures raise so the caller can log them without changing the
    already-recorded Ansible outcome.
    """
    if not _embedding_api_configured():
        logger.info("Skipping job-log indexing because no embedding API is configured")
        return False

    with _INDEX_LOCK:
        # Build the snapshot while holding the write lock so concurrently
        # finishing jobs cannot overwrite a newer snapshot with stale data.
        db = SessionLocal()
        try:
            job = db.query(Job).filter(Job.job_id == job_id).first()
            if not job or job.status not in TERMINAL_STATUSES:
                return False
            documents = build_job_documents(job) + build_fleet_snapshot_documents(db)
        finally:
            db.close()
        _index_documents(documents)
    return True


def start_reconcile() -> bool:
    """Start a best-effort background backfill of terminal jobs missing in Milvus."""
    global _reconcile_thread
    if not _embedding_api_configured():
        return False
    with _RECONCILE_LOCK:
        if _reconcile_thread and _reconcile_thread.is_alive():
            return False
        _reconcile_thread = threading.Thread(
            target=_reconcile_with_retry,
            daemon=True,
            name="job-log-reconcile",
        )
        _reconcile_thread.start()
    return True


def reconcile_terminal_jobs() -> int:
    """Backfill terminal database jobs that do not yet exist in the index."""
    if not _embedding_api_configured():
        return 0

    with _INDEX_LOCK:
        indexed_job_ids = _indexed_job_ids()

        db = SessionLocal()
        try:
            jobs = (
                db.query(Job)
                .filter(Job.status.in_(TERMINAL_STATUSES))
                .order_by(Job.finished_at.asc(), Job.created_at.asc())
                .all()
            )
            missing_jobs = [job for job in jobs if job.job_id not in indexed_job_ids]
            for job in missing_jobs:
                _index_documents(build_job_documents(job))
            _index_documents(build_fleet_snapshot_documents(db))
        finally:
            db.close()
    return len(missing_jobs)


def build_job_documents(job: Job) -> list[IndexDocument]:
    """Convert a completed job into bounded, retrieval-friendly log chunks."""
    finished_at = _format_datetime(job.finished_at or job.created_at)
    status = job.status or "unknown"
    targets = job.target_hosts or "none recorded"
    metadata = "\n".join(
        [
            "Document type: completed Fleet Manager operation log",
            f"Job ID: {job.job_id}",
            f"Terminal status: {status}",
            f"Playbook: {job.playbook}",
            f"Target hosts: {targets}",
            f"Started at (UTC): {_format_datetime(job.started_at)}",
            f"Finished at (UTC): {finished_at}",
            f"Duration seconds: {job.duration_seconds if job.duration_seconds is not None else 'unknown'}",
            f"Triggered by: {job.triggered_by or 'unknown'}",
            f"Error summary: {_one_line(job.error_summary or 'none', 2_000)}",
            f"Ansible recap:\n{_bounded_field(_sanitize_text(job.recap or 'not available'), 6_000)}",
        ]
    )
    output = _bounded_log(
        _sanitize_text(job.output_log or "No Ansible output was captured.")
    )
    chunks = _chunk_text(output)
    total = len(chunks)
    source = f"Fleet job {job.job_id}"
    documents = []
    for index, chunk in enumerate(chunks, start=1):
        text = f"{metadata}\n\nLog chunk {index} of {total}:\n{chunk}"
        documents.append(
            IndexDocument(
                document_id=f"job-{job.job_id}-{index:04d}",
                source=source,
                heading=f"{status.upper()} {job.playbook} on {targets} ({index}/{total})",
                text=text,
                job_id=job.job_id,
                status=status,
                finished_at=finished_at,
            )
        )
    return documents


def build_fleet_snapshot_documents(db) -> list[IndexDocument]:
    """Build a deterministic summary of the newest completed job per host."""
    hosts = db.query(Host).order_by(Host.hostname.asc()).all()
    jobs = (
        db.query(Job)
        .filter(Job.status.in_(TERMINAL_STATUSES))
        .order_by(Job.finished_at.desc(), Job.created_at.desc())
        .all()
    )

    latest_by_host: dict[str, Job] = {}
    registered = {host.hostname for host in hosts}
    for job in jobs:
        for hostname in _target_hostnames(job.target_hosts):
            if hostname in registered and hostname not in latest_by_host:
                latest_by_host[hostname] = job

    counts = {status: 0 for status in TERMINAL_STATUSES}
    outcome_hosts = {status: [] for status in TERMINAL_STATUSES}
    no_job_count = 0
    no_job_hosts = []
    host_lines = []
    for host in hosts:
        job = latest_by_host.get(host.hostname)
        if not job:
            no_job_count += 1
            no_job_hosts.append(host.hostname)
            host_lines.append(
                f"- {host.hostname}: no completed job; recorded host state={host.status or 'unknown'}; "
                f"last seen={_format_datetime(host.last_seen)}; reboot required={bool(host.reboot_required)}"
            )
            continue
        counts[job.status] = counts.get(job.status, 0) + 1
        outcome_hosts.setdefault(job.status, []).append(host.hostname)
        detail = _one_line(
            job.error_summary or job.recap or "no error or recap recorded", 500
        )
        host_lines.append(
            f"- {host.hostname}: latest job={job.status}; playbook={job.playbook}; "
            f"job_id={job.job_id}; finished={_format_datetime(job.finished_at or job.created_at)}; "
            f"recorded host state={host.status or 'unknown'}; last seen={_format_datetime(host.last_seen)}; "
            f"reboot required={bool(host.reboot_required)}; detail={detail}"
        )

    recent_lines = []
    for job in jobs[:RECENT_JOB_COUNT]:
        detail = _one_line(
            job.error_summary or job.recap or "no error or recap recorded", 700
        )
        recent_lines.append(
            f"- {_format_datetime(job.finished_at or job.created_at)} | {job.status} | {job.playbook} | "
            f"targets={job.target_hosts or 'none recorded'} | job_id={job.job_id} | {detail}"
        )

    generated_at = datetime.now(timezone.utc).isoformat()
    summary = "\n".join(
        [
            "Document type: current Fleet Manager device operation snapshot",
            f"Snapshot generated at (UTC): {generated_at}",
            (
                "Interpretation: For each registered host, the latest completed job that targeted that host is "
                "shown. This is job outcome evidence, not a live health probe. Prefer newer timestamps over older "
                "log chunks."
            ),
            f"Registered hosts: {len(hosts)}",
            (
                f"Latest per-host outcomes: success={counts.get('success', 0)}, failed={counts.get('failed', 0)}, "
                f"cancelled={counts.get('cancelled', 0)}, no completed job={no_job_count}"
            ),
            f"Hosts whose latest completed job failed: {_host_list(outcome_hosts.get('failed', []))}",
            f"Hosts whose latest completed job was cancelled: {_host_list(outcome_hosts.get('cancelled', []))}",
            f"Hosts with no completed job: {_host_list(no_job_hosts)}",
            "",
            "Latest completed job per registered host:",
            *(host_lines or ["- No registered hosts."]),
            "",
            f"Most recent {min(len(jobs), RECENT_JOB_COUNT)} completed jobs:",
            *(recent_lines or ["- No completed jobs."]),
        ]
    )

    chunks = _chunk_text(summary)
    total = len(chunks)
    return [
        IndexDocument(
            document_id=f"fleet-snapshot-{index:04d}",
            source="Current fleet job status",
            heading=f"Latest completed jobs by host ({index}/{total})",
            text=chunk,
            job_id=SNAPSHOT_JOB_ID,
            status="snapshot",
            finished_at=generated_at,
        )
        for index, chunk in enumerate(chunks, start=1)
    ]


def _index_documents(documents: list[IndexDocument]) -> None:
    if not documents:
        return
    vectors = _embed_texts([document.text for document in documents])
    if not vectors:
        raise RuntimeError("Embedding endpoint returned no vectors for job logs")
    collection = _get_or_create_collection(len(vectors[0]))

    # A snapshot can change its chunk count, so remove all prior snapshot rows.
    # Normal job IDs and chunk IDs are immutable and safe to upsert directly.
    if any(document.job_id == SNAPSHOT_JOB_ID for document in documents):
        collection.delete(expr=f'job_id == "{SNAPSHOT_JOB_ID}"')

    data = [
        [document.document_id for document in documents],
        [document.source[:256] for document in documents],
        [document.heading[:512] for document in documents],
        [document.text[:16_384] for document in documents],
        [document.job_id[:64] for document in documents],
        [document.status[:32] for document in documents],
        [document.finished_at[:64] for document in documents],
        vectors,
    ]
    collection.upsert(data)
    collection.flush()
    collection.load()


def _indexed_job_ids() -> set[str]:
    try:
        from pymilvus import Collection, connections, utility

        _connect(connections)
        if not utility.has_collection(COLLECTION_NAME, using=COLLECTION_ALIAS):
            return set()
        collection = Collection(COLLECTION_NAME, using=COLLECTION_ALIAS)
        collection.load()
        vector_field = next(
            field for field in collection.schema.fields if field.name == "vector"
        )
        existing_dim = int(vector_field.params["dim"])
        if settings.embed_dim and existing_dim != settings.embed_dim:
            return set()
        iterator = collection.query_iterator(
            batch_size=1_000,
            limit=-1,
            expr=f'job_id != "" and job_id != "{SNAPSHOT_JOB_ID}"',
            output_fields=["job_id"],
        )
        job_ids = set()
        try:
            while rows := iterator.next():
                job_ids.update(row["job_id"] for row in rows if row.get("job_id"))
        finally:
            iterator.close()
        return job_ids
    except Exception:
        logger.warning("Could not inspect the existing job-log index", exc_info=True)
        return set()


def _get_or_create_collection(embed_dim: int):
    from pymilvus import (
        Collection,
        CollectionSchema,
        DataType,
        FieldSchema,
        connections,
        utility,
    )

    _connect(connections)
    if utility.has_collection(COLLECTION_NAME, using=COLLECTION_ALIAS):
        collection = Collection(COLLECTION_NAME, using=COLLECTION_ALIAS)
        vector_field = next(
            field for field in collection.schema.fields if field.name == "vector"
        )
        existing_dim = int(vector_field.params["dim"])
        if existing_dim != embed_dim:
            # This index is fully derived from the database and can be rebuilt.
            logger.warning(
                "Recreating %s because embedding dimension changed from %s to %s",
                COLLECTION_NAME,
                existing_dim,
                embed_dim,
            )
            utility.drop_collection(COLLECTION_NAME, using=COLLECTION_ALIAS)
        else:
            collection.load()
            return collection

    fields = [
        FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=128, is_primary=True),
        FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=256),
        FieldSchema(name="heading", dtype=DataType.VARCHAR, max_length=512),
        FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=16_384),
        FieldSchema(name="job_id", dtype=DataType.VARCHAR, max_length=64),
        FieldSchema(name="status", dtype=DataType.VARCHAR, max_length=32),
        FieldSchema(name="finished_at", dtype=DataType.VARCHAR, max_length=64),
        FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=embed_dim),
    ]
    schema = CollectionSchema(
        fields, description="Redacted Fleet Manager completed operation logs"
    )
    collection = Collection(COLLECTION_NAME, schema, using=COLLECTION_ALIAS)
    collection.create_index(
        field_name="vector",
        index_params={
            "index_type": "IVF_FLAT",
            "metric_type": "L2",
            "params": {"nlist": 64},
        },
    )
    return collection


def _connect(connections) -> None:
    if not connections.has_connection(COLLECTION_ALIAS):
        connections.connect(alias=COLLECTION_ALIAS, uri=settings.milvus_uri, timeout=5)


def _embed_texts(texts: list[str]) -> list[list[float]]:
    all_vectors: list[list[float]] = []
    api_key = settings.embed_api_key or settings.ai_helper_api_key
    base_url = settings.embed_base_url or settings.ai_helper_base_url
    for start in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = texts[start : start + EMBED_BATCH_SIZE]
        request = urllib.request.Request(
            base_url.rstrip("/") + "/embeddings",
            data=json.dumps(
                {
                    "model": settings.embed_model,
                    "input": batch,
                    "encoding_format": "float",
                    "input_type": "passage",
                }
            ).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                result = json.loads(response.read())
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:1_000]
            raise RuntimeError(
                f"Job-log embedding request failed ({exc.code}): {body}"
            ) from exc
        rows = sorted(result["data"], key=lambda item: item["index"])
        all_vectors.extend(item["embedding"] for item in rows)
    return all_vectors


def _embedding_api_configured() -> bool:
    return bool(
        settings.embed_model
        and (settings.embed_api_key or settings.ai_helper_api_key)
        and (settings.embed_base_url or settings.ai_helper_base_url)
    )


def _reconcile_with_retry() -> None:
    delays = (0, 5, 20, 60)
    for attempt, delay in enumerate(delays, start=1):
        if delay:
            time.sleep(delay)
        try:
            count = reconcile_terminal_jobs()
            logger.info("Job-log index reconciliation added %s missing jobs", count)
            return
        except Exception:
            logger.warning(
                "Job-log index reconciliation attempt %s/%s failed",
                attempt,
                len(delays),
                exc_info=True,
            )


def _chunk_text(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    text = text.strip()
    if not text:
        return ["No content recorded."]
    chunks: list[str] = []
    current = ""
    for line in text.splitlines():
        segments = [
            line[index : index + max_chars] for index in range(0, len(line), max_chars)
        ] or [""]
        for segment in segments:
            candidate = f"{current}\n{segment}" if current else segment
            if current and len(candidate) > max_chars:
                chunks.append(current.strip())
                current = segment
            else:
                current = candidate
    if current.strip():
        chunks.append(current.strip())
    return chunks or ["No content recorded."]


def _bounded_log(text: str) -> str:
    if len(text) <= MAX_INDEXED_LOG_CHARS:
        return text
    head_chars = MAX_INDEXED_LOG_CHARS * 2 // 5
    tail_chars = MAX_INDEXED_LOG_CHARS - head_chars
    omitted = len(text) - MAX_INDEXED_LOG_CHARS
    return (
        text[:head_chars]
        + f"\n\n[... {omitted} log characters omitted from the retrieval index; full log remains in job history ...]\n\n"
        + text[-tail_chars:]
    )


def _sanitize_text(value: str) -> str:
    value = _PRIVATE_KEY_RE.sub("***REDACTED PRIVATE KEY***", value)
    value = _BEARER_RE.sub(r"\1***REDACTED***", value)
    return _SECRET_ASSIGNMENT_RE.sub(r"\1***REDACTED***", value)


def _target_hostnames(target_hosts: str | None) -> list[str]:
    return [
        hostname.strip()
        for hostname in (target_hosts or "").split(",")
        if hostname.strip()
    ]


def _format_datetime(value: datetime | None) -> str:
    if value is None:
        return "unknown"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _one_line(value: str, max_chars: int) -> str:
    compact = " ".join(_sanitize_text(value).split())
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 3] + "..."


def _host_list(hostnames: list[str]) -> str:
    return ", ".join(hostnames) if hostnames else "none"


def _bounded_field(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    head_chars = max_chars // 3
    tail_chars = max_chars - head_chars
    return value[:head_chars] + "\n[... field truncated ...]\n" + value[-tail_chars:]
