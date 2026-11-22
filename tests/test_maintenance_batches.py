"""Exercise the maintenance play headers on local inventory aliases."""

import asyncio
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.database import Base
from backend.models import Device, DeviceReservation, Job
from backend.routers import operations
from backend.schemas import OperationRunRequest
from backend.services import ansible_runner


PLAYBOOKS = Path(__file__).resolve().parents[1] / "playbooks"
ANSIBLE = shutil.which("ansible-playbook")


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        for hostname in ("first", "second", "unselected"):
            device = Device(hostname=hostname, transport="ssh", os_family="Debian",
                            facts_stale=False, discovered_at=datetime.now(timezone.utc))
            device.capabilities = ["system.update"]
            session.add(device)
        session.commit()
        yield session
    engine.dispose()


def test_only_batch_aware_operations_offer_a_batch_size(db):
    catalog = operations.list_operations(db, "operator")
    assert {op.id for op in catalog if op.supports_batch_size} == {"system.reboot", "system.update"}
    with pytest.raises(HTTPException) as error:
        asyncio.run(operations.run_operation("system.scan", OperationRunRequest(device_ids=[1], batch_size=1), db, "operator"))
    assert error.value.status_code == 400
    assert db.query(Job).count() == 0


@pytest.mark.parametrize("size", [0, -1, 2, True, 1.5, "1", "100%"])
def test_batch_size_must_be_an_integer_within_the_distinct_target_count(size):
    with pytest.raises(ValidationError):
        OperationRunRequest(device_ids=[1, 1], batch_size=size)


@pytest.mark.parametrize("operation", ["system.reboot", "system.update"])
@pytest.mark.parametrize("size", [None, 1])
def test_batch_plan_survives_acceptance_and_exact_retries(db, monkeypatch, operation, size):
    # Reserve real rows but never start a worker or contact inventory.
    monkeypatch.setattr(ansible_runner, "track_task", lambda coroutine: coroutine.close())
    payload = dict(device_ids=[1, 2], confirmation="first, second", request_key="batch-plan-fixture")
    expected_vars = {}
    if size is not None:
        payload["batch_size"] = size
        expected_vars["maintenance_batch_size"] = size
    if operation == "system.update":
        plans = {"first": "a" * 64, "second": "b" * 64}
        db.add(Job(job_id="a" * 36, playbook="package_preview.yml", target_hosts="first,second",
                   status="success", finished_at=datetime.now(timezone.utc)))
        db.commit()
        reports = [{"report_type": "packages", "hostname": name, "fingerprint": value} for name, value in plans.items()]
        monkeypatch.setattr(operations, "get_job_results", lambda job_id: reports)
        payload["preview_job_id"] = "a" * 36
        expected_vars["fleet_approved_package_plans"] = plans
    def submit(**options):
        request = OperationRunRequest(**{**payload, **options})
        return asyncio.run(operations.run_operation(operation, request, db, "operator"))

    accepted = submit()
    job = db.query(Job).filter_by(job_id=accepted["job_id"]).one()
    assert json.loads(job.extra_vars) == expected_vars
    assert job.target_hosts == "first,second"
    assert {r.device_id for r in db.query(DeviceReservation)} == {1, 2}
    assert submit()["job_id"] == job.job_id
    with pytest.raises(HTTPException) as error:
        submit(batch_size=1 if size is None else None)
    assert error.value.status_code == 409
    assert db.query(Job).filter_by(request_key=payload["request_key"]).count() == 1


@pytest.mark.skipif(not ANSIBLE, reason="ansible-playbook is required")
@pytest.mark.parametrize("batch_size", [None, 1, 2])
def test_maintenance_host_batches(tmp_path, batch_size):
    hosts = ["node-a", "node-b", "node-c"]
    inventory = tmp_path / "inventory.yml"
    groups = {}
    plays = []
    width = batch_size or len(hosts)
    batches = {name: hosts[i:i + width] for i in range(0, len(hosts), width) for name in hosts[i:i + width]}
    for name in (
        "system_update", "reboot", "service_control", "install_docker", "driver_upgrade",
        "firmware_update", "fabric_manager", "mig_management", "host_drain", "reachy_app_reset",
    ):
        header = yaml.safe_load((PLAYBOOKS / f"{name}.yml").read_text())[0]
        groups[header["hosts"]] = {"hosts": dict.fromkeys(hosts + ["unselected"], {})}
        plays.append({
            **{k: header[k] for k in ("name", "hosts", "serial", "strategy") if k in header},
            "gather_facts": False,
            "vars": {"expected_batches": batches},
            "tasks": [{"ansible.builtin.assert": {
                "that": ["ansible_play_batch | sort == expected_batches[inventory_hostname]"],
            }}],
        })
    inventory.write_text(yaml.safe_dump({"all": {"children": groups}}))
    playbook = tmp_path / "batches.yml"
    playbook.write_text(yaml.safe_dump(plays))
    cmd = [ANSIBLE, "-i", str(inventory), "--connection", "local", "--limit", ",".join(hosts), str(playbook)]
    if batch_size is not None:
        cmd.extend(["-e", json.dumps({"maintenance_batch_size": batch_size})])
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=40, env={**os.environ, "ANSIBLE_NOCOLOR": "1"})
    assert result.returncode == 0, result.stdout + result.stderr
    assert all(f"ok: [{host}]" in result.stdout for host in hosts)
