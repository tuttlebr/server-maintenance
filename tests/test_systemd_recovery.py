"""Run the production health checks with local, read-only command fixtures."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).parents[1]
ANSIBLE = shutil.which("ansible-playbook")
PLYMOUTH_JOB = "193 plymouth-quit-wait.service start running\n2 multi-user.target start waiting\n"
FAILED_UNIT = "example.service loaded failed failed Example service\n"
MOTD_UNIT = "motd-news.service loaded failed failed Message of the Day\n"


@pytest.mark.skipif(not ANSIBLE, reason="ansible-playbook is required")
@pytest.mark.parametrize("state,health_rc,failed_units,failed_rc,query_stderr,jobs_rc,service_mgr,ignored_units,expected_rc", [
    ("running\n", 0, "", 0, "", 0, "systemd", None, 0),
    ("  running \n", 0, " \n", 0, "", 0, "systemd", None, 0),
    ("starting\n", 1, "", 0, "", 0, "systemd", None, 2),
    ("starting\n", 1, "", 0, "Failed to list jobs", 1, "systemd", None, 2),
    ("degraded\n", 1, FAILED_UNIT, 0, "", 0, "systemd", None, 2),
    ("maintenance\n", 1, "", 0, "", 0, "systemd", None, 2),
    ("offline\n", 1, "", 0, "", 0, "systemd", None, 2),
    ("", 1, "", 1, "Failed to connect to bus", 1, "systemd", None, 2),
    ("running\n", 1, "", 0, "", 0, "systemd", None, 2),
    ("running\n", 0, FAILED_UNIT, 0, "", 0, "systemd", None, 2),
    ("running\n", 0, "", 1, "Failed to list units", 0, "systemd", None, 2),
    ("", 1, "", 1, "", 1, "openrc", None, 0),
    ("degraded\n", 1, MOTD_UNIT, 0, "", 0, "systemd", None, 0),
    ("degraded\n", 1, "  " + MOTD_UNIT + "\n", 0, "", 0, "systemd", None, 0),
    ("running\n", 0, MOTD_UNIT, 0, "", 0, "systemd", None, 0),
    ("degraded\n", 1, MOTD_UNIT + FAILED_UNIT, 0, "", 0, "systemd", None, 2),
    ("degraded\n", 1, "", 0, "", 0, "systemd", None, 2),
    ("degraded\n", 2, MOTD_UNIT, 0, "Failed to read state", 0, "systemd", None, 2),
    ("starting\n", 1, MOTD_UNIT, 0, "", 0, "systemd", None, 2),
    ("maintenance\n", 1, MOTD_UNIT, 0, "", 0, "systemd", None, 2),
    ("degraded\n", 1, MOTD_UNIT, 1, "Failed to list units", 0, "systemd", None, 2),
    ("degraded\n", 1, MOTD_UNIT.replace(".service", ".service-extra"), 0, "", 0, "systemd", None, 2),
    ("degraded\n", 1, MOTD_UNIT, 0, "", 0, "systemd", [], 2),
    ("degraded\n", 1, FAILED_UNIT, 0, "", 0, "systemd", ["example.service"], 0),
])
def test_systemd_health_diagnostics(
    tmp_path, state, health_rc, failed_units, failed_rc, query_stderr, jobs_rc, service_mgr, ignored_units, expected_rc,
):
    fakebin = tmp_path / "bin"
    fakebin.mkdir()
    calls = tmp_path / "systemctl.jsonl"
    responses = {
        "is-system-running": (state, query_stderr, health_rc),
        "list-units": (failed_units, query_stderr, failed_rc),
        "list-jobs": (PLYMOUTH_JOB if not jobs_rc else "", query_stderr, jobs_rc),
    }
    systemctl = fakebin / "systemctl"
    systemctl.write_text(
        f"#!{sys.executable}\n"
        "import json, sys\n"
        f"with open({str(calls)!r}, 'a') as log: log.write(json.dumps(sys.argv[1:]) + '\\n')\n"
        f"responses = {responses!r}\n"
        "stdout, stderr, rc = responses[sys.argv[1]]\n"
        "sys.stdout.write(stdout)\n"
        "sys.stderr.write(stderr)\n"
        "sys.exit(rc)\n"
    )
    systemctl.chmod(0o700)
    for name in ("findmnt", "awk"):
        executable = fakebin / name
        executable.write_text("#!/bin/sh\nexit 0\n")
        executable.chmod(0o700)

    playbook = tmp_path / "health.yml"
    playbook.write_text(yaml.safe_dump([{
        "name": "Verify systemd recovery diagnostics",
        "hosts": "localhost", "connection": "local", "gather_facts": False,
        "vars": {
            "ansible_python_interpreter": sys.executable,
            "ansible_facts": {"service_mgr": service_mgr, "os_family": "test"},
            **({"fleet_systemd_ignored_units": ignored_units} if ignored_units is not None else {}),
        },
        "environment": {"PATH": f"{fakebin}:{os.environ.get('PATH', '')}"},
        "tasks": [{
            "name": "Run production health verification",
            "ansible.builtin.include_tasks": str(ROOT / "playbooks/tasks/verify_host_health.yml"),
        }],
    }]))
    config = tmp_path / "ansible.cfg"
    config.write_text("[defaults]\nretry_files_enabled = False\n")
    result = subprocess.run(
        [ANSIBLE, "-i", "localhost,", str(playbook)], capture_output=True, text=True, timeout=30,
        env={**os.environ, "ANSIBLE_CONFIG": str(config), "ANSIBLE_NOCOLOR": "1"},
    )
    output = result.stdout + result.stderr
    assert result.returncode == expected_rc, output
    assert "changed=0" in result.stdout, output
    recorded = [json.loads(line) for line in calls.read_text().splitlines()] if calls.exists() else []
    if service_mgr != "systemd":
        assert not recorded
        return
    assert recorded[0] == ["list-units", "--failed", "--no-legend", "--no-pager", "--plain"]
    assert any(call[0] == "list-jobs" for call in recorded) == (health_rc != 0 or state.strip() != "running")
    if expected_rc:
        assert f"System state: {state.strip() or 'unknown'} (rc={health_rc})" in output
        assert f"Failed units (rc={failed_rc})" in output
        for line in failed_units.splitlines():
            if line.strip():
                assert line.split()[0] in output
        if state.strip() == "starting" and not jobs_rc:
            assert "plymouth-quit-wait.service" in output
            assert "multi-user.target" in output
        if query_stderr:
            assert query_stderr in output
    elif failed_units.strip():
        assert "Recovery permits non-critical failed units:" in output
        assert failed_units.split()[0] in output
