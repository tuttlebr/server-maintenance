import asyncio
import json
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, inspect
from sqlalchemy.orm import sessionmaker

from backend.auth import get_current_user, verify_admin
from backend.database import Base, get_db
from backend.models import Device, Job, ManagedUser, UserHostAssociation
from backend.routers import context, devices, jobs, users
from backend.schemas import DeviceUpdate
from backend.services import ansible_runner, inventory_writer, tokens


@pytest.fixture
def database(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path}/review.db", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, autoflush=False)
    monkeypatch.setattr(ansible_runner, "SessionLocal", sessions)
    monkeypatch.setattr(ansible_runner.settings, "data_dir", tmp_path)
    monkeypatch.setattr(ansible_runner.settings, "inventory_file", tmp_path / "inventory.json")
    with sessions() as db:
        yield db, sessions, engine
    engine.dispose()


@pytest.fixture
def client(database):
    _, sessions, _ = database
    app = FastAPI()
    for router in (jobs.router, devices.router, users.router, context.router):
        app.include_router(router)
    def session():
        with sessions() as db:
            yield db
    app.dependency_overrides[get_db] = session
    app.dependency_overrides[get_current_user] = lambda: "review"
    with TestClient(app) as client:
        yield client


def test_unicode_login_credentials_are_compared_without_server_error(monkeypatch):
    from backend.auth import settings
    monkeypatch.setattr(settings, "admin_username", "admin")
    monkeypatch.setattr(settings, "admin_password", "long Unicode password café")
    assert verify_admin("admin", "long Unicode password café")
    assert not verify_admin("管理员", "wrong")
    assert not verify_admin("admin", "密码")


@pytest.mark.parametrize("token", ["é.e.e", "e.e.é", "Bearer ", "a.b.c"])
def test_malformed_tokens_raise_auth_error(token):
    with pytest.raises(tokens.TokenError):
        tokens.decode_token(token, "test-secret")


@pytest.mark.parametrize("header,payload", [
    ([], {"sub": "admin", "exp": 200}),
    ({"alg": "HS256"}, []),
    ({"alg": "HS256"}, {"sub": "admin", "exp": 100}),
    ({"alg": "HS256"}, {"sub": [], "exp": 200}),
    ({"alg": "HS256"}, {"sub": "", "exp": 200}),
])
def test_signed_tokens_validate_claim_types_and_expiry(header, payload, monkeypatch):
    monkeypatch.setattr(tokens.time, "time", lambda: 100)
    message = f"{tokens._json_b64(header)}.{tokens._json_b64(payload)}"
    with pytest.raises(tokens.TokenError):
        tokens.decode_token(f"{message}.{tokens._sign(message, 'test-secret')}", "test-secret")


def test_empty_bearer_stream_header_returns_401():
    app = FastAPI()
    app.include_router(jobs.router)
    with TestClient(app) as client:
        assert client.get("/api/v2/jobs/any/stream", headers={"Authorization": "Bearer   "}).status_code == 401


def test_job_lists_omit_logs_without_loading_them_and_details_retain_them(database, client):
    db, _, engine = database
    db.add(Job(job_id="large-job", playbook="host_facts.yml", status="success", output_log="x" * 1_000_000,
               extra_vars='{"internal":"metadata"}'))
    db.commit()
    statements = []
    event.listen(engine, "before_cursor_execute", lambda conn, cursor, sql, *args: statements.append(sql))
    response = client.get("/api/v2/jobs", follow_redirects=False)
    assert response.status_code == 200
    assert len(response.content) < 2000
    assert "output_log" not in response.json()[0] and "extra_vars" not in response.json()[0]
    assert all("jobs.output_log" not in sql and "jobs.extra_vars" not in sql for sql in statements)
    assert len(client.get("/api/v2/jobs/large-job").json()["output_log"]) == 1_000_000


def test_adverse_pagination_is_global_and_stable_for_tied_timestamps(database, client):
    db, _, _ = database
    for i, status in enumerate(["failed", "partial", "success", "recovery_required", "failed", "pending"]):
        db.add(Job(job_id=f"job-{i}", playbook="host_facts.yml", status=status,
                   created_at=datetime(2026, 1, 1, tzinfo=timezone.utc)))
    db.commit()
    first = client.get("/api/v2/jobs?status=adverse&limit=2").json()
    second = client.get("/api/v2/jobs?status=adverse&limit=2&offset=2").json()
    assert [row["job_id"] for row in first + second] == ["job-4", "job-3", "job-1", "job-0"]
    overview = client.get("/api/v2/jobs/overview").json()
    assert overview["active_count"] == 1
    assert len(overview["recent"]) == 6 and len(overview["adverse"]) == 4
    assert overview["active"][0]["job_id"] == "job-5"


@pytest.mark.parametrize("limit", [-1, 0, 201])
def test_job_pagination_rejects_unbounded_limits(client, limit):
    assert client.get(f"/api/v2/jobs?limit={limit}").status_code == 422


def test_user_listing_uses_two_queries_for_many_accounts(database, client):
    db, _, engine = database
    host = Device(hostname="node")
    db.add(host)
    db.flush()
    for index in range(40):
        user = ManagedUser(username=f"user{index}")
        db.add(user)
        db.flush()
        db.add(UserHostAssociation(user_id=user.id, host_id=host.id, state="observed", managed_sudo=False))
    db.commit()
    statements = []
    event.listen(engine, "before_cursor_execute", lambda conn, cursor, sql, *args: statements.append(sql))
    response = client.get("/api/v2/users")
    assert response.status_code == 200 and len(response.json()) == 40
    assert len(statements) == 2
    assert response.json()[0]["placements"][0]["state"] == "observed"


def test_endpoint_change_invalidates_all_machine_observations(database):
    db, _, _ = database
    host = Device(hostname="node", endpoint="old.example", vendor="Old vendor", model="Old GPU server",
                  gpu_model="Old GPU", disk_root_percent=99, memory_gb=128, facts_stale=False,
                  discovered_at=datetime.now(timezone.utc), last_seen=datetime.now(timezone.utc))
    user = ManagedUser(username="jane")
    db.add_all([host, user])
    db.flush()
    association = UserHostAssociation(user_id=user.id, host_id=host.id, state="observed", managed_sudo=True,
                                      sudo_policy="old privilege")
    db.add(association)
    db.commit()
    result = devices.update_device(host.id, DeviceUpdate(endpoint="new.example"), db, "review")
    assert result.facts_stale and result.last_seen is None
    assert result.model is None and result.gpu_model is None and result.disk_root_percent is None
    assert result.memory_gb is None and result.discovered_at is None
    assert association.state == "unverified" and association.managed_sudo is None and association.sudo_policy is None


def test_daemon_port_change_cannot_bypass_recovery(database):
    from fastapi import HTTPException
    db, _, _ = database
    host = Device(hostname="robot", transport="reachy_daemon", daemon_port=8000, recovery_required=True)
    db.add(host)
    db.commit()
    with pytest.raises(HTTPException) as caught:
        devices.update_device(host.id, DeviceUpdate(daemon_port=8001), db, "review")
    assert caught.value.status_code == 409


def test_scan_unknown_capacity_stays_unknown_and_failed_report_rolls_back(database, tmp_path, monkeypatch):
    db, _, _ = database
    db.add_all([Device(hostname="bad", gpu_model="Original"), Device(hostname="good", disk_root_percent=80)])
    db.commit()
    scan_dir = tmp_path / "scan"
    scan_dir.mkdir()
    for name in ("bad", "good"):
        (scan_dir / f"{name}.json").write_text(json.dumps({"hostname": name, "gpu_model": "Uncommitted GPU", "disk_root_percent": "unknown"}))
    original = ansible_runner.enrich_from_scan
    def enrich(host, report):
        if host.hostname == "bad":
            raise ValueError("malformed discovery")
        return original(host, report)
    monkeypatch.setattr(ansible_runner, "enrich_from_scan", enrich)
    errors = ansible_runner._process_scan_results(["bad", "good"], scan_dir=scan_dir)
    db.expire_all()
    assert len(errors) == 1
    assert db.query(Device).filter_by(hostname="bad").one().gpu_model == "Original"
    good = db.query(Device).filter_by(hostname="good").one()
    assert good.disk_root_percent is None and good.disk_raid_percent is None


def test_inventory_refresh_uses_latest_committed_identity(database, tmp_path):
    db, sessions, _ = database
    host = Device(hostname="node", endpoint="old.example")
    db.add(host)
    db.commit()
    assert host.endpoint == "old.example"
    with sessions() as other:
        other.query(Device).filter_by(id=host.id).update({"endpoint": "new.example"})
        other.commit()
    inventory_writer.regenerate_inventory(db)
    inventory = json.loads((tmp_path / "inventory.json").read_text())
    assert inventory["all"]["children"]["managed_hosts"]["hosts"]["node"]["ansible_host"] == "new.example"


def test_job_summary_query_defers_large_columns(database):
    db, sessions, _ = database
    db.add(Job(job_id="job", playbook="host_facts.yml", output_log="large log", extra_vars="{}"))
    db.commit()
    with sessions() as fresh:
        row = jobs.list_jobs(limit=50, offset=0, db=fresh, user="review")[0]
        assert {"output_log", "extra_vars"} <= inspect(row).unloaded


def test_failed_startup_releases_executor_lease(tmp_path, monkeypatch):
    from backend import main
    from backend.services.execution_state import acquire_executor_lock
    monkeypatch.setattr(main.settings, "data_dir", tmp_path)
    monkeypatch.setattr(type(main.settings), "validate_runtime_settings", lambda self: None)
    monkeypatch.setattr(main, "initialize_known_hosts", lambda: None)
    def fail():
        raise RuntimeError("migration unavailable")
    monkeypatch.setattr(main, "init_db", fail)
    async def startup():
        with pytest.raises(RuntimeError, match="migration unavailable"):
            async with main.lifespan(main.app):
                pytest.fail("Startup unexpectedly succeeded")
    asyncio.run(startup())
    assert ansible_runner._EXECUTOR_LEASE is None
    with acquire_executor_lock():
        pass
