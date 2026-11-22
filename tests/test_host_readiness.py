import asyncio
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import yaml
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend.models import Device, Job
from backend.services import ansible_runner as runner
from playbooks.files import host_readiness as readiness


ROOT = Path(__file__).resolve().parents[1]


def test_pressure_services_and_reboot_are_actionable(tmp_path, monkeypatch):
    monkeypatch.setattr(os, "statvfs", lambda _: SimpleNamespace(
        f_blocks=100, f_bfree=20, f_bavail=10, f_frsize=1024, f_flag=0))
    meminfo = tmp_path / "meminfo"
    meminfo.write_text("MemTotal: 102400 kB\nMemAvailable: 4096 kB\n")
    services = "\n".join(f"worker-{i}.service loaded failed failed Worker" for i in range(19))
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: SimpleNamespace(stdout=services, returncode=0))
    marker = tmp_path / "reboot-required"
    marker.touch()
    checks = [
        readiness.root_capacity(), readiness.available_memory(meminfo), readiness.failed_services(),
        readiness.reboot_request(marker, tmp_path),
    ]
    assert all(c["status"] == "attention" and c["advice"] for c in checks)
    assert "4.0%" in checks[1]["detail"]
    assert "19 failed" in checks[2]["detail"] and "worker-18.service" not in checks[2]["detail"]


def test_missing_observations_are_distinct_from_clear_checks(tmp_path, monkeypatch):
    assert readiness.available_memory(tmp_path / "missing")["status"] == "unavailable"
    for content in ("MemTotal: 1000 kB\n", "MemTotal: 1000 kB\nMemAvailable: 0 bytes\n"):
        meminfo = tmp_path / "meminfo"
        meminfo.write_text(content)
        assert readiness.available_memory(meminfo)["status"] == "unavailable"
    meminfo.write_text("MemTotal: 1000 kB\nMemAvailable: 100 kB\n")
    assert readiness.available_memory(meminfo)["status"] == "ok"
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: SimpleNamespace(stdout="", returncode=1))
    assert readiness.failed_services()["status"] == "unavailable"
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: SimpleNamespace(stdout="", returncode=0))
    assert readiness.failed_services()["status"] == "ok"
    assert readiness.reboot_request(tmp_path / "missing", tmp_path / "non-debian")["status"] == "not_applicable"
    assert readiness.reboot_request(tmp_path / "missing", tmp_path)["status"] == "ok"


def test_read_only_root_and_capacity_boundary(monkeypatch):
    fs = SimpleNamespace(f_blocks=100, f_bfree=15, f_bavail=15, f_frsize=1024, f_flag=0)
    monkeypatch.setattr(os, "statvfs", lambda _: fs)
    assert readiness.root_capacity()["status"] == "attention"
    fs.f_bavail = fs.f_bfree = 16
    assert readiness.root_capacity()["status"] == "ok"
    fs.f_flag = os.ST_RDONLY
    assert "read-only" in readiness.root_capacity()["detail"]


def test_real_playbook_saves_only_selected_fixture_host(tmp_path):
    # Isolate the managed host, including /proc and systemd, from the machine
    # running this test. The real play handles collection, decoding and saving.
    interpreter = tmp_path / "fixture-python"
    checks = {key: {"status": "ok", "detail": "Recorded on selected fixture."}
              for key in ("root_capacity", "memory", "services", "reboot")}
    interpreter.write_text(
        f"#!{sys.executable}\nimport os,sys\n"
        "if sys.argv[1].endswith('host_readiness.py'):\n"
        f"    print({json.dumps(checks)!r})\n"
        "else:\n"
        f"    os.execv({sys.executable!r}, [{sys.executable!r}] + sys.argv[1:])\n"
    )
    interpreter.chmod(0o700)
    inventory = tmp_path / "hosts.yml"
    inventory.write_text(yaml.safe_dump({"all": {"children": {"managed_hosts": {
        "hosts": {"selected": {}, "other": {}},
        "vars": {"ansible_connection": "local", "ansible_python_interpreter": str(interpreter)},
    }}}}))
    ansible = shutil.which("ansible-playbook")
    assert ansible, "Use scripts/check-backend.sh to run the Ansible fixtures"
    config = tmp_path / "ansible.cfg"
    config.write_text("[defaults]\nretry_files_enabled = False\n")
    result = subprocess.run(
        [ansible, "-i", str(inventory), str(ROOT / "playbooks/host_readiness.yml"), "--limit", "selected",
         "-e", json.dumps({"__fleet_results_dir": str(tmp_path / "results"), "__fleet_job_id": "fixture"})],
        cwd=tmp_path, env={**os.environ, "ANSIBLE_CONFIG": str(config)}, capture_output=True, text=True, timeout=40,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    paths = list((tmp_path / "results/fixture").glob("*.json"))
    assert len(paths) == 1
    report = json.loads(paths[0].read_text())
    assert report["hostname"] == "selected" and report["report_type"] == "host_readiness"
    assert report["schema_version"] == 1 and report["timestamp"]
    assert report["checks"] == checks


def test_successful_recap_requires_a_complete_report_for_each_host(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path}/fleet.db")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    monkeypatch.setattr(runner, "SessionLocal", sessions)
    monkeypatch.setattr(runner.settings, "data_dir", tmp_path)
    monkeypatch.setattr(runner, "_JOB_SEMAPHORE", None)
    monkeypatch.setattr(runner.job_log_indexer, "ingest_completed_job", lambda *args: None)

    async def execute(playbook, targets, values, credentials, job_id, timeout):
        directory = tmp_path / "job-results" / job_id
        directory.mkdir(parents=True)
        checks = {key: {"status": "attention", "detail": "Fixture finding", "advice": "Review it."}
                  for key in ("root_capacity", "memory", "services", "reboot")}
        for name, readings in [("complete", checks), ("incomplete", {"memory": checks["memory"]})]:
            (directory / f"{name}.json").write_text(json.dumps({
                "schema_version": 1, "report_type": "host_readiness", "hostname": name, "checks": readings,
            }))
        runner.get_log_path(job_id).write_text("PLAY RECAP\n" + "".join(
            f"{name} : ok=3 changed=0 unreachable=0 failed=0\n" for name in targets))
        return 0

    monkeypatch.setattr(runner, "_execute", execute)

    async def run():
        with sessions() as db:
            names = ["complete", "incomplete", "missing"]
            for name in names:
                db.add(Device(hostname=name, transport="ssh", facts_stale=False, recovery_required=name == "complete",
                              discovered_at=datetime.now(timezone.utc)))
            db.commit()
            await runner.run_playbook(db, "host_readiness.yml", hosts=names)
        await asyncio.gather(*list(runner._BACKGROUND_TASKS))

    asyncio.run(run())
    with sessions() as db:
        job = db.query(Job).one()
        assert job.status == "partial" and job.execution_kind == "read_only"
        assert {item["hostname"]: item["status"] for item in job.device_results} == {
            "complete": "success", "incomplete": "verification_failed", "missing": "verification_failed",
        }
        assert all(not host.facts_stale for host in db.query(Device))
        assert {host.hostname for host in db.query(Device) if host.recovery_required} == {"complete"}
    engine.dispose()
