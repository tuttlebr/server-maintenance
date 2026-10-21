"""Exercise hourly discovery against durable jobs and real device reservations."""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend.models import Device, DeviceReservation, Job
from backend.services import ansible_runner as runner
from backend.services import scan_scheduler as scheduler
from backend.services.execution_state import acquire_executor_lock


@pytest.fixture
def fleet(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path}/fleet.db")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    monkeypatch.setattr(scheduler, "SessionLocal", sessions)
    monkeypatch.setattr(runner, "SessionLocal", sessions)
    monkeypatch.setattr(runner.settings, "data_dir", tmp_path)
    monkeypatch.setattr(runner, "_JOB_SEMAPHORE", None)
    monkeypatch.setattr(runner, "regenerate_inventory", lambda db: None)
    monkeypatch.setattr(runner.job_log_indexer, "index_completed_job", AsyncMock())

    async def execute(playbook, targets, values, credentials, job_id, timeout):
        assert playbook == "host_facts.yml"
        directory = tmp_path / "scans" / job_id
        directory.mkdir(parents=True, exist_ok=True)
        for name in targets:
            (directory / f"{name}.json").write_text(json.dumps({
                "hostname": name, "os_family": "Debian", "service_manager": "systemd",
            }))
        runner.get_log_path(job_id).write_text("PLAY RECAP\n" + "\n".join(
            f"{name} : ok=1 changed=0 unreachable=0 failed=0" for name in targets
        ))
        return 0

    monkeypatch.setattr(runner, "_execute", execute)
    monkeypatch.setattr(runner, "probe_reachy", lambda *args: {
        "reachable": False, "detail": "Device offline", "facts": {},
    })
    yield sessions
    engine.dispose()


async def finish_jobs():
    await asyncio.gather(*list(runner._BACKGROUND_TASKS))


def test_scans_idle_supported_devices_and_catches_up_busy_devices(fleet):
    with fleet() as db:
        node = Device(hostname="node", transport="ssh", recovery_required=True, recovery_reason="Unfinished change")
        robot = Device(hostname="robot", transport="reachy_daemon", status="offline")
        busy = Device(hostname="busy", transport="ssh")
        db.add_all([node, robot, busy, Device(hostname="unsupported", transport="other")])
        db.add(Job(job_id="maintenance", playbook="system_update.yml", status="running"))
        db.flush()
        db.add(DeviceReservation(device_id=busy.id, job_id="maintenance"))
        db.commit()

    async def exercise():
        job_id = await scheduler.enqueue_due_scan()
        # A concurrent scheduler pass cannot queue another automatic scan.
        assert await scheduler.enqueue_due_scan() is None
        await finish_jobs()
        with fleet() as db:
            job = db.query(Job).filter_by(job_id=job_id).one()
            assert job.target_hosts == "node,robot"
            assert job.triggered_by == "Automatic hourly scan"
            assert job.execution_kind == "read_only" and job.status == "partial"
            assert {r["hostname"] for r in job.device_results} == {"node", "robot"}
            node = db.query(Device).filter_by(hostname="node").one()
            assert not node.facts_stale and node.discovered_at
            assert node.recovery_required and node.recovery_reason == "Unfinished change"
            assert db.query(Device).filter_by(hostname="robot").one().facts_stale
            assert db.query(DeviceReservation).count() == 1
        # Failed/offline devices are not hammered on each minute's poll.
        assert await scheduler.enqueue_due_scan() is None
        with fleet() as db:
            db.query(DeviceReservation).delete()
            db.query(Job).filter_by(job_id="maintenance").update({"status": "success"})
            db.commit()
        catchup_id = await scheduler.enqueue_due_scan()
        await finish_jobs()
        with fleet() as db:
            assert db.query(Job).filter_by(job_id=catchup_id).one().target_hosts == "busy"
            assert not db.query(DeviceReservation).count()
        assert await scheduler.enqueue_due_scan() is None

    asyncio.run(exercise())


@pytest.mark.parametrize("status", ["success", "failed", "partial", "cancelled"])
@pytest.mark.parametrize("trigger", ["admin", scheduler.TRIGGERED_BY])
def test_hourly_cadence_uses_persisted_manual_and_automatic_attempts(fleet, status, trigger):
    accepted_at = datetime.now(timezone.utc).replace(microsecond=0)
    with fleet() as db:
        db.add(Device(hostname="node", transport="ssh"))
        db.add(Job(job_id="previous", playbook="host_facts.yml", target_hosts="node",
                   status=status, triggered_by=trigger, created_at=accepted_at))
        db.commit()

    # Separate event loops simulate scheduler restarts; no in-memory timer state.
    assert asyncio.run(scheduler.enqueue_due_scan(now=accepted_at + timedelta(minutes=59, seconds=59))) is None

    async def exercise():
        job_id = await scheduler.enqueue_due_scan(now=accepted_at + timedelta(hours=1))
        await finish_jobs()
        return job_id

    job_id = asyncio.run(exercise())
    with fleet() as db:
        assert db.query(Job).count() == 2
        assert db.query(Job).filter_by(job_id=job_id).one().status == "success"


def test_overdue_active_scan_prevents_another_scheduled_job(fleet):
    with fleet() as db:
        db.add(Device(hostname="new-device", transport="ssh"))
        db.add(Job(job_id="long-scan", playbook="host_facts.yml", target_hosts="other",
                   status="running", triggered_by=scheduler.TRIGGERED_BY,
                   created_at=datetime.now(timezone.utc) - timedelta(hours=2)))
        db.commit()
    assert asyncio.run(scheduler.enqueue_due_scan()) is None
    with fleet() as db:
        assert db.query(Job).count() == 1


def test_empty_fleet_does_not_create_a_job(fleet):
    assert asyncio.run(scheduler.enqueue_due_scan()) is None
    with fleet() as db:
        assert db.query(Job).count() == 0


def test_recent_targets_match_exact_names(fleet):
    with fleet() as db:
        db.add_all([Device(hostname="node"), Device(hostname="node-01")])
        db.add(Job(job_id="manual", playbook="host_facts.yml", target_hosts="node-01", status="success"))
        db.commit()

    async def exercise():
        job_id = await scheduler.enqueue_due_scan()
        await finish_jobs()
        with fleet() as db:
            assert db.query(Job).filter_by(job_id=job_id).one().target_hosts == "node"

    asyncio.run(exercise())


def test_scheduler_retries_errors_and_propagates_shutdown(monkeypatch, caplog):
    enqueue = AsyncMock(side_effect=[RuntimeError("database unavailable"), None])
    sleep = AsyncMock(side_effect=[None, asyncio.CancelledError()])
    monkeypatch.setattr(scheduler, "enqueue_due_scan", enqueue)
    monkeypatch.setattr(scheduler.asyncio, "sleep", sleep)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(scheduler.run_scan_scheduler())
    assert enqueue.await_count == 2
    assert [call.args for call in sleep.await_args_list] == [(60,), (60,)]
    assert "retrying in 60 seconds" in caplog.text


@pytest.mark.parametrize("enabled", [True, False])
def test_lifespan_stops_scheduler_before_executor_and_releases_lease(fleet, monkeypatch, enabled):
    from backend import main

    events = []
    monkeypatch.setattr(main, "SessionLocal", fleet)
    monkeypatch.setattr(main.settings, "automatic_scan_enabled", enabled)
    monkeypatch.setattr(type(main.settings), "validate_runtime_settings", lambda self: None)
    for name in ("initialize_known_hosts", "init_db", "encrypt_existing_host_secrets", "start_job_log_reconcile"):
        monkeypatch.setattr(main, name, lambda: None)
    monkeypatch.setattr(main, "regenerate_inventory", lambda db: None)

    async def run_scheduler():
        events.append("scheduler started")
        try:
            await asyncio.Event().wait()
        finally:
            events.append("scheduler stopped")

    async def shutdown():
        events.append("executor stopped")

    monkeypatch.setattr(main, "run_scan_scheduler", run_scheduler)
    monkeypatch.setattr(main, "shutdown_executor", shutdown)

    async def exercise():
        async with main.lifespan(main.app):
            await asyncio.sleep(0)
            with pytest.raises(RuntimeError, match="Another Fleet executor"):
                acquire_executor_lock()
            assert events == (["scheduler started"] if enabled else [])

    asyncio.run(exercise())
    assert events == (["scheduler started", "scheduler stopped", "executor stopped"] if enabled else ["executor stopped"])
    assert runner._EXECUTOR_LEASE is None
    with acquire_executor_lock():
        pass
