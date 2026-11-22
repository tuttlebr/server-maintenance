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
SPARK_BOOT_JOBS = """\
198 getty.target                         start waiting
2   multi-user.target                    start waiting
201 system-getty.slice                   start waiting
235 plymouth-quit-wait.service           start running
205 serial-getty@ttyS0.service           start waiting
188 systemd-update-utmp-runlevel.service start waiting
1   graphical.target                     start waiting
35  setvtrgb.service                     start waiting
"""


def run_health_check(
    tmp_path, *, state="starting", health_rc=1, failed_units="", failed_rc=0, query_stderr="",
    jobs=PLYMOUTH_JOB, jobs_rc=0, service_mgr="systemd", ignored_units=None, spark=False, standalone=True,
):
    fakebin = tmp_path / "bin"
    fakebin.mkdir()
    calls = tmp_path / "systemctl.jsonl"
    responses = {
        "is-system-running": (state, query_stderr, health_rc),
        "list-units": (failed_units, query_stderr, failed_rc),
        "list-jobs": (jobs, query_stderr, jobs_rc),
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
    play = yaml.safe_load((ROOT / "playbooks/recovery_check.yml").read_text())[0]
    (tmp_path / "tasks").symlink_to(ROOT / "playbooks/tasks", target_is_directory=True)
    if not standalone:
        # Exercise the shared health check as used by the legacy resume play.
        play["tasks"] = [{"ansible.builtin.include_tasks": "tasks/verify_host_health.yml"}]
    play.update({
        "connection": "local", "gather_facts": False, "become": False,
        "vars": {
            "ansible_python_interpreter": sys.executable,
            "ansible_facts": {"service_mgr": service_mgr, "os_family": "test"},
            **({"fleet_systemd_ignored_units": ignored_units} if ignored_units is not None else {}),
        },
        "environment": {"PATH": f"{fakebin}:{os.environ.get('PATH', '')}"},
    })
    playbook.write_text(yaml.safe_dump([play]))
    inventory = tmp_path / "hosts.ini"
    inventory.write_text("[managed_hosts]\nlocalhost\n" + ("[dgx_spark]\nlocalhost\n" if spark else ""))
    config = tmp_path / "ansible.cfg"
    config.write_text("[defaults]\nretry_files_enabled = False\n")
    result = subprocess.run(
        [ANSIBLE, "-i", str(inventory), str(playbook)], capture_output=True, text=True, timeout=30,
        env={**os.environ, "ANSIBLE_CONFIG": str(config), "ANSIBLE_NOCOLOR": "1"},
    )
    recorded = [json.loads(line) for line in calls.read_text().splitlines()] if calls.exists() else []
    return result, recorded


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
    result, recorded = run_health_check(
        tmp_path, state=state, health_rc=health_rc, failed_units=failed_units, failed_rc=failed_rc,
        query_stderr=query_stderr, jobs_rc=jobs_rc, service_mgr=service_mgr, ignored_units=ignored_units,
        jobs=PLYMOUTH_JOB if not jobs_rc else "",
    )
    output = result.stdout + result.stderr
    assert result.returncode == expected_rc, output
    assert "changed=0" in result.stdout, output
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


@pytest.mark.skipif(not ANSIBLE, reason="ansible-playbook is required")
@pytest.mark.parametrize("overrides,accepted", [
    pytest.param({"jobs": SPARK_BOOT_JOBS}, True, id="observed-spark-boot"),
    pytest.param({}, True, id="subset-of-console-jobs"),
    pytest.param({"standalone": False}, False, id="shared-resume-check"),
    pytest.param({"jobs": ""}, False, id="empty-job-list"),
    pytest.param({"jobs": "2 multi-user.target start waiting"}, False, id="missing-plymouth"),
    pytest.param({"jobs": PLYMOUTH_JOB + "9 data.mount start waiting"}, False, id="pending-mount"),
    pytest.param({"jobs": PLYMOUTH_JOB.replace("start waiting", "start running")}, False, id="other-running-job"),
    pytest.param({"jobs": PLYMOUTH_JOB.replace("start running", "stop running")}, False, id="stopping-plymouth"),
    pytest.param({"jobs_rc": 1}, False, id="incomplete-job-query"),
    pytest.param({"failed_rc": 1}, False, id="failed-unit-query"),
    pytest.param({"failed_units": MOTD_UNIT}, False, id="failed-unit-during-boot"),
    pytest.param({"state": "maintenance"}, False, id="unexpected-system-state"),
])
def test_spark_splash_wait(tmp_path, overrides, accepted):
    result, _ = run_health_check(tmp_path, spark=True, **overrides)
    output = result.stdout + result.stderr
    assert result.returncode == (0 if accepted else 2), output
    assert "changed=0" in output
    assert ("DGX Spark boot splash is still active" in output) == accepted
    if not accepted:
        assert "System services need recovery." in output
