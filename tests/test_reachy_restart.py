import asyncio
import itertools
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.capabilities import OPERATION_BY_ID, REACHY_DAEMON_RESTART, operation_ineligibility
from backend.database import Base
from backend.models import Device, DeviceReservation, Job
from backend.routers import operations
from backend.schemas import OperationRunRequest
from backend.services import ansible_runner


def mini(hostname="reachy-mini", **values):
    device = Device(hostname=hostname, endpoint=f"{hostname}.local", daemon_port=8000,
                    **{"transport": "reachy_daemon", "kind": "robot", "model": "Reachy Mini Wireless", **values})
    device.capabilities = [REACHY_DAEMON_RESTART]
    return device


def healthy():
    return {"reachable": True, "facts": {"daemon": {"state": "running", "backend_status": {"ready": True}}}}


@pytest.fixture
def setup(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path}/test.db", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    queued = []
    monkeypatch.setattr(operations, "SessionLocal", sessions)
    monkeypatch.setattr(operations, "track_task", queued.append)
    monkeypatch.setattr(operations, "get_log_path", lambda job_id: tmp_path / f"{job_id}.log")
    monkeypatch.setattr(ansible_runner, "_JOB_SEMAPHORE", None)
    monkeypatch.setattr(operations, "probe_reachy", lambda *args: healthy())
    with sessions() as db:
        db.add(mini())
        db.commit()
        yield db, queued
    for coroutine in queued:
        coroutine.close()
    engine.dispose()


def dispatch(db, ids=None, confirmation="reachy-mini", key="reachy-restart-request-key", user="test"):
    return asyncio.run(operations.run_operation(REACHY_DAEMON_RESTART, OperationRunRequest(
        device_ids=ids or [db.query(Device).first().id], confirmation=confirmation, request_key=key), db, user))


@pytest.mark.parametrize("values", [
    {"transport": "ssh"}, {"kind": "server"}, {"model": "Reachy 2"},
    {"model": "Other Robot"}, {"model": "Reachy Miniature"}, {"model": None},
])
def test_restart_rejects_other_devices_even_with_the_capability(values):
    assert "Requires a Reachy Mini" in operation_ineligibility(mini(**values), OPERATION_BY_ID[REACHY_DAEMON_RESTART])


@pytest.mark.parametrize("model", ["Reachy Mini", "Reachy Mini Wireless", "Reachy Mini Lite", "reachy-mini"])
def test_restart_supports_reachy_mini_variants(model):
    assert operation_ineligibility(mini(model=model), OPERATION_BY_ID[REACHY_DAEMON_RESTART]) is None


def test_restart_requires_capability_and_prior_recovery(setup):
    db, queued = setup
    host = db.query(Device).one()
    host.capabilities = []
    db.commit()
    with pytest.raises(HTTPException, match="Required capability"):
        dispatch(db)
    host.capabilities = [REACHY_DAEMON_RESTART]
    host.recovery_required = True
    db.commit()
    with pytest.raises(HTTPException, match="previous Reachy operation"):
        dispatch(db)
    assert not queued


def test_catalog_and_dispatch_reject_mixed_targets_before_starting(setup):
    db, queued = setup
    other = mini("compute-01", transport="ssh", kind="server", model="Server")
    db.add(other)
    db.commit()
    operation = next(op for op in operations.list_operations(db, "test") if op.id == REACHY_DAEMON_RESTART)
    assert operation.eligible_device_ids == [db.query(Device).filter_by(hostname="reachy-mini").one().id]
    assert operation.excluded_devices[0]["id"] == other.id
    assert operation.confirmation == "confirm"
    with pytest.raises(HTTPException, match="Requires a Reachy Mini"):
        dispatch(db, [d.id for d in db.query(Device).all()], "compute-01, reachy-mini")
    assert not queued
    assert not db.query(Job).count()


def test_confirmation_is_required_and_unknown_ids_never_start(setup):
    db, queued = setup
    with pytest.raises(HTTPException) as error:
        dispatch(db, confirmation="")
    assert error.value.status_code == 400
    with pytest.raises(HTTPException) as error:
        dispatch(db, [1, 999], "reachy-mini")
    assert error.value.status_code == 404
    assert not queued


def test_restart_reserves_devices_and_retries_reconnect_without_restarting(setup):
    db, queued = setup
    accepted = dispatch(db)
    job = db.query(Job).one()
    assert job.playbook == REACHY_DAEMON_RESTART
    assert job.execution_kind == "mutation" and job.phase == "queued"
    assert db.query(DeviceReservation).one().job_id == accepted["job_id"]
    with pytest.raises(HTTPException, match="reserved"):
        dispatch(db, key="another-restart-request-key")
    # An ambiguous retry must reconnect even after an interruption marks recovery.
    db.query(Device).one().recovery_required = True
    db.commit()
    assert dispatch(db, confirmation="")["job_id"] == accepted["job_id"]
    assert len(queued) == 1
    with pytest.raises(HTTPException, match="different operation"):
        dispatch(db, user="someone-else")
    other = mini("reachy-second")
    db.add(other)
    db.commit()
    with pytest.raises(HTTPException, match="different operation"):
        dispatch(db, [other.id], "reachy-second")
    with pytest.raises(HTTPException, match="different operation"):
        asyncio.run(operations.run_operation("system.reboot", OperationRunRequest(
            device_ids=[1], request_key=job.request_key), db, "test"))


def test_restart_calls_only_restart_then_tracks_job_and_verifies_health(setup, monkeypatch):
    db, queued = setup
    db.add(mini("reachy-second"))
    db.commit()
    calls = []
    def request(endpoint, port, path, **kwargs):
        calls.append((endpoint, path, kwargs.get("method", "GET")))
        if path == "/api/daemon/restart":
            assert kwargs["method"] == "POST"
            return {"job_id": f"remote-{endpoint}"}
        assert path == "/update/info"
        assert kwargs["query"]["job_id"] == f"remote-{endpoint}"
        return {"status": "done", "logs": ["Restart complete"]}
    monkeypatch.setattr(operations, "reachy_request", request)
    result = dispatch(db, [d.id for d in db.query(Device).all()], "reachy-mini, reachy-second")
    asyncio.run(queued.pop())
    db.expire_all()
    job = db.query(Job).filter_by(job_id=result["job_id"]).one()
    assert job.status == "success"
    assert [item["status"] for item in job.device_results] == ["success", "success"]
    assert all(item["remote_job_id"].startswith("remote-") for item in job.device_results)
    assert [call[1] for call in calls] == ["/api/daemon/restart", "/update/info"] * 2
    assert calls[0][0] == calls[1][0] and calls[2][0] == calls[3][0] != calls[0][0]
    assert "Daemon running; robot backend ready" in job.output_log
    assert all(not d.facts_stale and d.status == "online" for d in db.query(Device).all())
    assert not db.query(DeviceReservation).count()


@pytest.mark.parametrize("response,expected", [
    ({}, "recovery_required"), (RuntimeError("Connection lost"), "recovery_required"),
    (RuntimeError("Reachy daemon returned HTTP 409: Daemon is busy."), "failed"),
])
def test_start_failure_is_not_replayed_and_reports_uncertainty(setup, monkeypatch, response, expected):
    db, queued = setup
    calls = []
    def request(*args, **kwargs):
        calls.append(args)
        if isinstance(response, Exception):
            raise response
        return response
    monkeypatch.setattr(operations, "reachy_request", request)
    dispatch(db)
    asyncio.run(queued.pop())
    db.expire_all()
    job = db.query(Job).one()
    assert job.status == expected
    assert job.device_results[0]["detail"]
    assert db.query(Device).one().recovery_required == (expected == "recovery_required")
    assert not db.query(DeviceReservation).count()
    assert len(calls) == 1


def test_health_verification_waits_through_startup(setup, monkeypatch):
    db, queued = setup
    observations = iter([{"reachable": False, "detail": "Disconnected"},
                         {"reachable": True, "facts": {"daemon": {"state": "starting"}}}, healthy()])
    monkeypatch.setattr(operations, "probe_reachy", lambda *args: next(observations))
    monkeypatch.setattr(operations.asyncio, "sleep", AsyncMock())
    monkeypatch.setattr(operations, "reachy_request", lambda *args, **kwargs: {"job_id": "remote-1"})
    monkeypatch.setattr(operations, "_poll_reachy_job", AsyncMock())
    dispatch(db)
    asyncio.run(queued.pop())
    db.expire_all()
    assert db.query(Job).one().status == "success"
    assert operations.asyncio.sleep.await_count == 2


@pytest.mark.parametrize("observation", [
    {"reachable": True, "facts": {}},
    {"reachable": True, "facts": {"daemon": {"state": "running", "backend_status": {"ready": False}}}},
    {"reachable": True, "facts": {"daemon": {"state": "running", "error": "Motor error", "backend_status": {"ready": True}}}},
])
def test_reachable_is_not_enough_to_certify_restart_health(setup, monkeypatch, observation):
    db, queued = setup
    ticks = itertools.count(0, 35)
    monkeypatch.setattr(operations, "time", SimpleNamespace(monotonic=lambda: next(ticks)))
    monkeypatch.setattr(operations.asyncio, "sleep", AsyncMock())
    monkeypatch.setattr(operations, "probe_reachy", lambda *args: observation)
    monkeypatch.setattr(operations, "reachy_request", lambda *args, **kwargs: {"job_id": "remote-1"})
    monkeypatch.setattr(operations, "_poll_reachy_job", AsyncMock())
    dispatch(db)
    asyncio.run(queued.pop())
    db.expire_all()
    job = db.query(Job).one()
    assert job.status == "recovery_required"
    assert job.device_results[0]["remote_job_id"] == "remote-1"
    assert "health could not be verified" in job.error_summary
    assert db.query(Device).one().recovery_required
    assert not db.query(DeviceReservation).count()


def test_a_queued_job_that_is_no_longer_pending_never_restarts(setup, monkeypatch):
    db, queued = setup
    dispatch(db)
    db.query(Job).one().status = "cancelled"
    db.commit()
    request = AsyncMock()
    monkeypatch.setattr(operations, "reachy_request", request)
    asyncio.run(queued.pop())
    request.assert_not_called()


@pytest.mark.parametrize("remote_status,remote_id,healthy_backend,expected", [
    ("done", "remote-1", True, "success"), ("running", "remote-1", True, "failed"),
    ("done", None, True, "failed"), ("done", "remote-1", False, "failed"),
])
def test_scan_verifies_interrupted_restart_without_replaying(setup, monkeypatch, remote_status, remote_id, healthy_backend, expected):
    from backend.routers.devices import scan_device

    db, queued = setup
    host = db.query(Device).one()
    host.recovery_required = True
    host.recovery_reason = "Interrupted restart"
    db.add(Job(job_id="interrupted", playbook=REACHY_DAEMON_RESTART, target_hosts=host.hostname,
               execution_kind="mutation", status="recovery_required", outcomes_json=json.dumps([
                   {"hostname": host.hostname, "status": "recovery_required", "remote_job_id": remote_id}])))
    db.commit()
    calls = []
    def request(endpoint, port, path, **kwargs):
        calls.append(path)
        assert path == "/update/info" and kwargs.get("method", "GET") == "GET"
        assert kwargs["query"]["job_id"] == remote_id
        return {"status": remote_status}
    monkeypatch.setattr(operations, "reachy_request", request)
    if not healthy_backend:
        ticks = itertools.count(0, 35)
        monkeypatch.setattr(operations, "time", SimpleNamespace(monotonic=lambda: next(ticks)))
        monkeypatch.setattr(operations.asyncio, "sleep", AsyncMock())
        monkeypatch.setattr(operations, "probe_reachy", lambda *args: {"reachable": True, "facts": {}})
    result = asyncio.run(scan_device(host.id, db, "test"))
    assert db.query(Job).filter_by(job_id=result["job_id"]).one().status == expected
    assert host.recovery_required == (expected != "success")
    assert calls == (["/update/info"] if remote_id else [])
    assert not queued and not db.query(DeviceReservation).count()
