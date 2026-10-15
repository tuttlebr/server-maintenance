"""Discovery prerequisites use real persistence and fake device transports."""
import asyncio
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.capabilities import OPERATION_BY_ID, OPERATIONS, facts_are_stale, operation_ineligibility
from backend.database import Base
from backend.models import Device, DeviceReservation, Job
from backend.routers import operations, users
from backend.schemas import BulkUserAdd, OperationRunRequest
from backend.services import ansible_runner as runner
from backend.services.device_discovery import initial_profile
from backend.services.job_results import get_job_results


@pytest.fixture
def fleet(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path}/fleet.db")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    monkeypatch.setattr(runner, "SessionLocal", sessions)
    monkeypatch.setattr(runner.settings, "data_dir", tmp_path)
    monkeypatch.setattr(runner, "_JOB_SEMAPHORE", None)
    monkeypatch.setattr(runner, "regenerate_inventory", lambda db: None)
    monkeypatch.setattr(runner.job_log_indexer, "ingest_completed_job", lambda job_id: None)
    calls, behavior = [], {}
    with sessions() as db:
        node = Device(hostname="node", transport="ssh", facts_stale=True)
        robot = Device(hostname="robot", transport="reachy_daemon", endpoint="robot.local", facts_stale=True)
        db.add_all([node, robot, Device(hostname="unselected", transport="ssh")])
        db.commit()

    async def execute(playbook, targets, values, credentials, job_id, timeout, append=False):
        assert playbook == "host_facts.yml" and targets == ["node"]
        calls.append((playbook, targets))
        with sessions() as db:
            assert db.query(DeviceReservation).count() == len(db.query(Job).filter_by(job_id=job_id).one().target_hosts.split(","))
        directory = tmp_path / "scans" / job_id
        directory.mkdir(parents=True, exist_ok=True)
        if not behavior.get("missing_report"):
            (directory / "node.json").write_text(json.dumps({
                "hostname": "node", "os_family": "Debian", "os_version": "Ubuntu 24.04",
                "architecture": "x86_64", "service_manager": "systemd", "package_manager": "apt",
                "docker_available": True, "gpu_model": "NVIDIA test GPU", "gpu_vendor": "NVIDIA",
            }))
        failed = behavior.get("ssh_failed", False)
        runner.get_log_path(job_id).write_text(f"PLAY RECAP\nnode : ok=4 changed=0 unreachable=0 failed={int(failed)}\n")
        return behavior.get("rc", 2 if failed else 0)

    def probe(endpoint, port):
        calls.append(("daemon", endpoint))
        return {"reachable": not behavior.get("daemon_failed"), "detail": "Daemon observation",
                "facts": {"daemon": {"state": "running"}}, **initial_profile("reachy_daemon")}

    monkeypatch.setattr(runner, "_execute", execute)
    monkeypatch.setattr(runner, "probe_reachy", probe)

    async def scan(ids=(1, 2), retry=False):
        with sessions() as db:
            payload = OperationRunRequest(device_ids=list(ids), request_key="scan-request-key")
            result = await operations.run_operation("system.scan", payload, db, "test")
            if retry:
                assert await operations.run_operation("system.scan", payload, db, "test") == {
                    "job_id": result["job_id"], "detail": "Operation already accepted"}
                with pytest.raises(runner.PlaybookRequestError, match="reserved"):
                    await runner.run_playbook(db, "host_facts.yml", hosts=["node"])
        await asyncio.gather(*list(runner._BACKGROUND_TASKS))
        return result["job_id"]

    yield sessions, calls, behavior, scan
    engine.dispose()


def test_mixed_scan_persists_facts_and_unlocks_capabilities_once(fleet):
    sessions, calls, _, scan = fleet
    job_id = asyncio.run(scan(retry=True))
    assert calls == [("host_facts.yml", ["node"]), ("daemon", "robot.local")]
    with sessions() as db:
        job = db.query(Job).one()
        assert job.status == "success" and job.execution_kind == "read_only"
        assert {r["hostname"] for r in job.device_results} == {"node", "robot"}
        assert not db.query(DeviceReservation).count()
        node, robot, unselected = db.query(Device).order_by(Device.id).all()
        assert not facts_are_stale(node) and not facts_are_stale(robot)
        assert facts_are_stale(unselected)
        assert node.architecture == "x86_64" and node.facts["package_manager"] == "apt"
        assert operation_ineligibility(node, OPERATION_BY_ID["containers.cleanup"]) is None
        assert operation_ineligibility(node, OPERATION_BY_ID["gpu.inspect"]) is None
        assert operation_ineligibility(robot, OPERATION_BY_ID["reachy.daemon.restart"]) is None
        reports = get_job_results(job_id)
        assert {r["hostname"] for r in reports} == {"node", "robot"}
        assert all(r["report_type"] == "discovery" and r["observed_at"] for r in reports)


@pytest.mark.parametrize("failure", ["ssh_failed", "missing_report", "process_failure", "daemon_failed"])
def test_partial_scan_never_unlocks_failed_device_or_publishes_its_facts(fleet, failure):
    sessions, _, behavior, scan = fleet
    behavior[failure] = True
    if failure == "process_failure":
        behavior["rc"] = 1
    job_id = asyncio.run(scan())
    failed_name = "robot" if failure == "daemon_failed" else "node"
    with sessions() as db:
        assert db.query(Job).one().status == "partial"
        for host in db.query(Device).filter(Device.hostname.in_(["node", "robot"])):
            assert facts_are_stale(host) is (host.hostname == failed_name)
        assert not db.query(DeviceReservation).count()
    assert failed_name not in {r["hostname"] for r in get_job_results(job_id)}


def test_daemon_only_scan_never_invokes_ansible(fleet):
    sessions, calls, _, scan = fleet
    asyncio.run(scan(ids=(2,)))
    assert calls == [("daemon", "robot.local")]
    with sessions() as db:
        assert db.query(Job).one().status == "success"


def test_scan_preserves_existing_recovery_requirement(fleet):
    sessions, _, _, scan = fleet
    with sessions() as db:
        host = db.get(Device, 1)
        host.recovery_required = True
        host.recovery_reason = "Unfinished mutation"
        db.commit()
    asyncio.run(scan())
    with sessions() as db:
        assert db.get(Device, 1).recovery_reason == "Unfinished mutation"
        assert db.get(Device, 1).recovery_required
        assert not facts_are_stale(db.get(Device, 1))


@pytest.mark.parametrize("staleness", ["missing", "flagged", "expired"])
def test_every_other_operation_requires_current_discovery(fleet, staleness, monkeypatch):
    sessions, _, _, _ = fleet
    fake = AsyncMock()
    monkeypatch.setattr(operations, "run_playbook", fake)
    with sessions() as db:
        host = db.get(Device, 1)
        host.facts_stale = staleness == "flagged"
        host.discovered_at = None if staleness == "missing" else datetime.now(timezone.utc) - timedelta(hours=2 if staleness == "expired" else 0)
        db.commit()
        assert operation_ineligibility(host, OPERATION_BY_ID["system.scan"]) is None
        for operation in OPERATIONS:
            if operation.id == "system.scan":
                continue
            with pytest.raises(HTTPException, match="Scan devices first") as exc:
                asyncio.run(operations.run_operation(operation.id, OperationRunRequest(device_ids=[1], confirmation="node"), db, "test"))
            assert exc.value.status_code == 409
        fake.assert_not_awaited()


@pytest.mark.parametrize("playbook", ["package_preview.yml", "reboot.yml", "user_management.yml"])
def test_runner_rejects_unscanned_targets_without_reserving(fleet, playbook):
    sessions, calls, _, _ = fleet
    with sessions() as db:
        with pytest.raises(runner.PlaybookRequestError, match="Scan devices first"):
            asyncio.run(runner.run_playbook(db, playbook, hosts=["node"]))
        assert not db.query(Job).count() and not db.query(DeviceReservation).count()
    assert not calls


def test_account_api_cannot_bypass_discovery(fleet):
    sessions, calls, _, _ = fleet
    with sessions() as db:
        with pytest.raises(runner.PlaybookRequestError, match="Scan devices first"):
            asyncio.run(users.bulk_add_users(BulkUserAdd(device_ids=[1], users=[{"username": "sam", "full_name": "Sam"}]), db, "test"))
        assert not db.query(Job).count()
    assert not calls


def test_facts_expiring_in_queue_stop_the_action(fleet, monkeypatch):
    sessions, calls, _, _ = fleet
    queued = []
    monkeypatch.setattr(runner, "track_task", queued.append)
    with sessions() as db:
        host = db.get(Device, 1)
        host.facts_stale = False
        host.discovered_at = datetime.now(timezone.utc)
        db.commit()
        asyncio.run(runner.run_playbook(db, "reboot.yml", hosts=["node"]))
        host.discovered_at -= timedelta(hours=2)
        db.commit()
    asyncio.run(queued.pop())
    with sessions() as db:
        job = db.query(Job).one()
        assert job.status == "failed" and job.phase == "discovery_required"
        assert job.device_results == [{"hostname": "node", "status": "not_started"}]
        assert not db.query(DeviceReservation).count()
        assert not db.get(Device, 1).recovery_required
    assert not calls


def test_cancellation_during_daemon_scan_is_terminal_and_releases_reservations(fleet, monkeypatch):
    sessions, _, _, scan = fleet

    def probe(*args):
        with sessions() as db:
            runner.cancel_job(db.query(Job).one().job_id)
        return {"reachable": True, "detail": "Observed before stopping", "facts": {"daemon": {"state": "running"}}}

    monkeypatch.setattr(runner, "probe_reachy", probe)
    asyncio.run(scan())
    with sessions() as db:
        assert db.query(Job).one().status == "cancelled"
        assert not db.query(DeviceReservation).count()
        assert not db.get(Device, 2).recovery_required
