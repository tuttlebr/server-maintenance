import asyncio
import io
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from backend.auth import get_current_user
from backend.database import Base, get_db
from backend.models import Device, Job
from backend.routers import chat, devices, jobs
from backend.schemas import ChatRequest, DeviceUpdate
from backend.services import ansible_runner, docs_indexer, job_log_indexer
from nat.embedding_response import validate_embeddings


@pytest.fixture
def database(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path}/review.db", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    for module in (jobs, ansible_runner, job_log_indexer):
        monkeypatch.setattr(module, "SessionLocal", sessions)
    monkeypatch.setattr(ansible_runner.settings, "data_dir", tmp_path)
    monkeypatch.setattr(ansible_runner.settings, "inventory_file", tmp_path / "inventory.json")
    yield sessions, engine
    engine.dispose()


def test_progress_never_loads_logs_or_artifacts(database, monkeypatch):
    sessions, engine = database
    with sessions() as db:
        db.add(Job(job_id="job", playbook="host_facts.yml", status="running", output_log="x" * 1_000_000))
        db.commit()
    statements = []
    event.listen(engine, "before_cursor_execute", lambda conn, cursor, sql, *args: statements.append(sql))
    monkeypatch.setattr(jobs, "get_job_results", lambda *args: pytest.fail("Progress loaded artifacts"))
    app = FastAPI()
    app.include_router(jobs.router)
    def get_session():
        with sessions() as db:
            yield db
    app.dependency_overrides[get_db] = get_session
    app.dependency_overrides[get_current_user] = lambda: "test"
    with TestClient(app) as client:
        response = client.get("/api/v2/jobs/job/progress")
        assert response.status_code == 200
        assert response.json()["status"] == "running"
        assert "output_log" not in response.json()
        assert len(response.content) < 2000
        assert client.get("/api/v2/jobs/missing/progress").status_code == 404
    assert all("jobs.output_log" not in sql and "jobs.extra_vars" not in sql for sql in statements)


def test_stream_releases_connections_and_preserves_chunked_unicode(database):
    sessions, engine = database
    with sessions() as db:
        db.add(Job(job_id="stream", playbook="host_facts.yml", status="success"))
        db.commit()
    output = "x" * 65535 + "é\nsecond line\nunterminated"
    jobs.get_log_path("stream").write_text(output, encoding="utf-8")
    async def scenario():
        response = await jobs.stream_job_output("stream", user="test")
        assert engine.pool.checkedout() == 0
        events = []
        async for item in response.body_iterator:
            assert engine.pool.checkedout() == 0
            events.append(item)
        return events
    events = asyncio.run(scenario())
    assert events[-1] == "event: done\ndata: success\n\n"
    lines = [line[6:] for item in events[:-1] for line in item.splitlines() if line.startswith("data: ")]
    assert "\n".join(lines) == output


@pytest.mark.parametrize("hostname", ["storage_server", "gpu_usage_node", "driver_upgrade_node"])
def test_scan_names_are_not_mistaken_for_legacy_artifacts(database, tmp_path, hostname):
    sessions, _ = database
    with sessions() as db:
        db.add(Device(hostname=hostname, facts_stale=True))
        db.commit()
    scan_dir = tmp_path / "discovery"
    scan_dir.mkdir()
    (scan_dir / f"{hostname}.json").write_text(json.dumps({"hostname": hostname, "os_family": "Debian"}))
    assert ansible_runner._process_scan_results([hostname], scan_dir=scan_dir) == []
    with sessions() as db:
        host = db.query(Device).one()
        assert host.status == "online" and not host.facts_stale


@pytest.mark.parametrize("field", ["endpoint", "display_name"])
def test_blank_identity_edits_are_rejected(field):
    with pytest.raises(ValueError):
        DeviceUpdate(**{field: "   "})


def test_password_auth_cannot_silently_remain_key_auth(database):
    sessions, _ = database
    with sessions() as db:
        host = Device(hostname="node", transport="ssh")
        db.add(host)
        db.commit()
        with pytest.raises(HTTPException) as caught:
            devices.update_device(host.id, DeviceUpdate(passwordless_ssh=False), db, "test")
        assert caught.value.status_code == 422
        assert host.passwordless_ssh


@pytest.mark.parametrize("provider", ["nat", "direct"])
@pytest.mark.parametrize("ending", [b"", b'data: {"error":{"message":"provider failure"}}\n', b'data: broken\n'])
def test_upstream_chat_failure_never_reports_success(monkeypatch, provider, ending):
    monkeypatch.setattr(chat.settings, "nat_base_url", "http://provider.test")
    monkeypatch.setattr(chat.settings, "ai_helper_base_url", "http://provider.test")
    monkeypatch.setattr(chat, "_nat_available", lambda: provider == "nat")
    monkeypatch.setattr(chat, "_direct_llm_available", lambda: True)
    monkeypatch.setattr(chat.job_context, "get_job_context", lambda *args, **kwargs: "evidence")
    monkeypatch.setattr(chat.docs_loader, "get_relevant_sections", lambda *args, **kwargs: "")
    monkeypatch.setattr(chat.context_manager, "get_relevant_context", lambda *args, **kwargs: "")
    stream = io.BytesIO(b'data:{"choices":[{"delta":{"content":"partial"}}]}\n\n' + ending)
    monkeypatch.setattr(chat.urllib.request, "urlopen", lambda *args, **kwargs: stream)
    async def scenario():
        response = await chat.chat(ChatRequest(messages=[{"role": "user", "content": "Question"}]), user="test")
        return "".join([item async for item in response.body_iterator])
    events = asyncio.run(scenario())
    assert '"content": "partial"' in events
    assert '"type": "error"' in events
    assert "event: done" not in events
    assert stream.closed


def test_chat_disconnect_closes_provider_without_reading_more(monkeypatch):
    monkeypatch.setattr(chat.settings, "nat_base_url", "")
    monkeypatch.setattr(chat, "_direct_llm_available", lambda: True)
    monkeypatch.setattr(chat.job_context, "get_job_context", lambda *args, **kwargs: "evidence")
    consumed, closed = [], []
    def provider(*args):
        try:
            for number in range(100):
                consumed.append(number)
                yield {"type": "content", "content": str(number)}
        finally:
            closed.append(True)
    monkeypatch.setattr(chat, "_stream_from_llm", provider)
    async def scenario():
        response = await chat.chat(ChatRequest(messages=[{"role": "user", "content": "Question"}]), user="test")
        iterator = response.body_iterator
        await anext(iterator)  # initial status
        await anext(iterator)  # first provider token
        await iterator.aclose()
    asyncio.run(scenario())
    assert consumed == [0] and closed == [True]


def test_chat_cancel_during_provider_read_closes_after_that_read(monkeypatch):
    monkeypatch.setattr(chat.settings, "nat_base_url", "")
    monkeypatch.setattr(chat, "_direct_llm_available", lambda: True)
    monkeypatch.setattr(chat.job_context, "get_job_context", lambda *args, **kwargs: "evidence")
    started, release, closed = threading.Event(), threading.Event(), threading.Event()
    def provider(*args):
        try:
            started.set()
            assert release.wait(2)
            yield {"type":"content", "content":"last in-flight event"}
            pytest.fail("Cancelled chat consumed another event")
        finally:
            closed.set()
    monkeypatch.setattr(chat, "_stream_from_llm", provider)
    async def scenario():
        response = await chat.chat(ChatRequest(messages=[{"role":"user", "content":"Question"}]), user="test")
        await anext(response.body_iterator)
        task = asyncio.create_task(anext(response.body_iterator))
        try:
            for _ in range(100):
                if started.is_set():
                    break
                await asyncio.sleep(.001)
            assert started.is_set()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        finally:
            release.set()
        assert await asyncio.to_thread(closed.wait, 2)
    asyncio.run(scenario())


@pytest.mark.parametrize("rows", [
    [], [{"index": 1, "embedding": [1]}], [{"index": True, "embedding": [1]}],
    [{"index": 0, "embedding": []}], [{"index": 0, "embedding": [float("nan")]}],
    [{"index": 0, "embedding": [True]}], [{"index": 0, "embedding": ["1"]}],
])
def test_embedding_contract_rejects_malformed_vectors(rows):
    with pytest.raises(ValueError):
        validate_embeddings({"data": rows}, 1)


def test_embedding_mapping_and_dimension_validation():
    rows = [{"index": 1, "embedding": [2, 3]}, {"index": 0, "embedding": [0, 1]}]
    assert validate_embeddings({"data": rows}, 2, 2) == [[0, 1], [2, 3]]
    with pytest.raises(ValueError):
        validate_embeddings({"data": rows}, 2, 3)
    with pytest.raises(ValueError):
        validate_embeddings({"data": [rows[0], rows[0]]}, 2)


def test_invalid_embeddings_do_not_rebuild_or_delete_index(monkeypatch):
    monkeypatch.setattr(job_log_indexer.settings, "embed_dim", 2)
    monkeypatch.setattr(job_log_indexer.settings, "embed_base_url", "http://provider.test")
    monkeypatch.setattr(job_log_indexer.urllib.request, "urlopen", lambda *args, **kwargs: io.BytesIO(b'{"data":[]}'))
    monkeypatch.setattr(job_log_indexer, "_get_or_create_collection", lambda *args: pytest.fail("Invalid vectors reached Milvus"))
    document = job_log_indexer.IndexDocument("id", "source", "heading", "text", "job", "success", "now")
    with pytest.raises(ValueError):
        job_log_indexer._index_documents([document])


def test_fleet_index_snapshot_does_not_load_historical_logs(database):
    sessions, engine = database
    with sessions() as db:
        db.add(Device(hostname="node"))
        db.add(Job(job_id="job", playbook="host_facts.yml", target_hosts="node", status="success",
                   finished_at=datetime.now(timezone.utc), output_log="x" * 1_000_000))
        db.commit()
    statements = []
    event.listen(engine, "before_cursor_execute", lambda conn, cursor, sql, *args: statements.append(sql))
    with sessions() as db:
        assert job_log_indexer.build_fleet_snapshot_documents(db)
    assert all("jobs.output_log" not in sql for sql in statements)


def test_milvus_field_limits_count_utf8_bytes():
    value = job_log_indexer._utf8_prefix("界" * 300, 512)
    assert len(value.encode()) <= 512 and value == "界" * 170


def test_slow_indexing_cannot_starve_the_executor_used_for_fleet_work(monkeypatch):
    release, started = threading.Event(), threading.Event()
    def slow_index(job_id):
        started.set()
        assert release.wait(3)
        return True
    monkeypatch.setattr(job_log_indexer, "ingest_completed_job", slow_index)
    async def scenario():
        asyncio.get_running_loop().set_default_executor(ThreadPoolExecutor(max_workers=1))
        indexing = asyncio.create_task(job_log_indexer.index_completed_job("job"))
        try:
            for _ in range(100):
                if started.is_set():
                    break
                await asyncio.sleep(.001)
            assert started.is_set()
            assert await asyncio.wait_for(asyncio.to_thread(lambda: "fleet work"), timeout=.5) == "fleet work"
        finally:
            release.set()
            await indexing
    asyncio.run(scenario())


def test_index_status_caches_success_and_throttles_unavailable_count_checks(monkeypatch):
    monkeypatch.setattr(docs_indexer, "_state", {**docs_indexer._state, "running":False,"last_count":None})
    monkeypatch.setattr(docs_indexer, "_last_count_check", float("-inf"))
    clock, calls = [100.0], []
    monkeypatch.setattr(docs_indexer.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(docs_indexer, "_peek_count", lambda: calls.append(True))
    docs_indexer.get_status()
    docs_indexer.get_status()
    assert len(calls) == 1
    clock[0] += 31
    monkeypatch.setattr(docs_indexer, "_peek_count", lambda: 12)
    assert docs_indexer.get_status()["last_count"] == 12
    monkeypatch.setattr(docs_indexer, "_peek_count", lambda: pytest.fail("Known count was reloaded"))
    assert docs_indexer.get_status()["last_count"] == 12
