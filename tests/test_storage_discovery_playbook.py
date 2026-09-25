"""Exercise storage discovery diagnostics and host isolation through Ansible."""
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
pytestmark = pytest.mark.skipif(not ANSIBLE, reason="ansible-playbook is required")
DISCOVERY = ROOT / "playbooks/tasks/discover_storage.yml"


def run_playbook(tmp_path, play, inventory="localhost,"):
    playbook = tmp_path / "storage.yml"
    playbook.write_text(yaml.safe_dump([play]))
    config = tmp_path / "ansible.cfg"
    config.write_text("[defaults]\nretry_files_enabled = False\n")
    return subprocess.run(
        [ANSIBLE, "-i", inventory, str(playbook)], capture_output=True, text=True, timeout=30,
        env={**os.environ, "ANSIBLE_CONFIG": str(config), "ANSIBLE_NOCOLOR": "1"},
    )


@pytest.mark.parametrize("raw,expected", [
    (None, "Storage discovery result is missing"),
    ({}, "Storage discovery did not return an exit code"),
    ({"msg": "Unable to execute interpreter fixture"}, "Unable to execute interpreter fixture"),
    ({"skipped": True, "msg": "Command was skipped in check mode"}, "Command was skipped in check mode"),
    ({"rc": 17, "stderr": "missing required tool", "stdout": "partial discovery output"}, "command failed"),
    ({"rc": 1, "stderr": "", "stdout": "Python traceback merged into stdout\n[]"}, "Python traceback merged into stdout"),
])
@pytest.mark.parametrize("required", [True, False])
def test_discovery_failure_diagnostics(tmp_path, raw, expected, required):
    # Inject action results at the boundary, including failures before rc exists.
    tasks = yaml.safe_load(DISCOVERY.read_text())
    result_index = next(i for i, task in enumerate(tasks) if task["name"] == "Describe storage discovery outcome")
    variables = {"storage_discovery_executable": "/fixture/python", "storage_discovery_required": required}
    if raw is not None:
        variables["storage_discovery_raw"] = raw
    result = run_playbook(tmp_path, {
        "name": "Storage failure fixture", "hosts": "localhost", "gather_facts": False,
        "vars": variables,
        "tasks": tasks[result_index:] + [{
            "name": "Verify optional discovery remains usable",
            "ansible.builtin.assert": {"that": [
                "not storage_discovery_ok", "storage_mounts == []",
                "root_storage_mount == {}", "non_root_storage_mounts == []",
            ]},
        }],
    })
    output = result.stdout + result.stderr
    assert result.returncode == (2 if required else 0), output
    assert expected in output
    assert "Interpreter: /fixture/python" in output
    assert f"rc: {(raw or {}).get('rc', 'missing')}" in output
    for stream in ("stdout", "stderr"):
        value = (raw or {}).get(stream)
        if value:
            # The default callback JSON-escapes newlines in failure messages.
            for line in value.splitlines():
                assert line in output
    if not required:
        assert "All assertions passed" in output


@pytest.mark.parametrize("mode", ["explicit", "gathered", "discovered", "auto", "auto_silent", "auto_legacy", "auto_legacy_silent"])
def test_discovery_interpreter_selection_without_module_dependencies(tmp_path, mode):
    interpreter = tmp_path / "python-fixture"
    interpreter.write_text(f"#!{sys.executable}\nprint('[]')\n")
    interpreter.chmod(0o700)
    files = tmp_path / "files"
    files.mkdir()
    shutil.copy(ROOT / "playbooks/files/storage_discovery.py", files)
    variables = {"storage_discovery_required": True}
    if mode == "explicit":
        variables.update({
            "ansible_python_interpreter": str(interpreter),
            "ansible_facts": {"python": {"executable": "/stale/fact/python"}},
        })
    elif mode == "gathered":
        variables["ansible_facts"] = {"python": {"executable": str(interpreter)}}
    else:
        variables["ansible_facts"] = {"discovered_interpreter_python": str(interpreter)}
        if mode != "discovered":
            variables["ansible_python_interpreter"] = mode
    result = run_playbook(tmp_path, {
        "name": "Storage interpreter fixture", "hosts": "localhost", "connection": "local", "gather_facts": False,
        "vars": variables,
        "tasks": [{"ansible.builtin.include_tasks": str(DISCOVERY)}, {
            "name": "Verify successful discovery",
            "ansible.builtin.assert": {"that": ["storage_discovery_ok", "storage_mounts == []"]},
        }],
    })
    assert result.returncode == 0, result.stdout + result.stderr
    assert "All assertions passed" in result.stdout


def test_storage_analysis_failure_keeps_other_host_report(tmp_path):
    interpreter = tmp_path / "python-fixture"
    mounts = [{"mountpoint": "/", "source": "/dev/mapper/vg-root", "type": "local", "entries": []}]
    interpreter.write_text(
        f"#!{sys.executable}\n"
        "import os, sys\n"
        "if any(arg.endswith('storage_discovery.py') for arg in sys.argv[1:]):\n"
        "    if os.environ.get('STORAGE_TEST_HOST') == 'broken':\n"
        "        print('discovery stdout evidence')\n"
        "        sys.stderr.write('discovery stderr evidence\\n')\n"
        "        sys.exit(42)\n"
        f"    print({json.dumps(mounts)!r})\n"
        "    sys.exit(0)\n"
        f"os.execv({sys.executable!r}, [{sys.executable!r}] + sys.argv[1:])\n"
    )
    interpreter.chmod(0o700)
    shutil.copytree(ROOT / "playbooks/tasks", tmp_path / "tasks")
    (tmp_path / "files").mkdir()
    shutil.copy(ROOT / "playbooks/files/storage_discovery.py", tmp_path / "files")
    inventory = tmp_path / "inventory.yml"
    inventory.write_text(yaml.safe_dump({"all": {"children": {"managed_hosts": {
        "hosts": {"broken": {}, "healthy": {}},
        "vars": {"ansible_connection": "local", "ansible_python_interpreter": str(interpreter)},
    }}}}))
    # Execute the full production play; redirect its temporary report to this test.
    source = (ROOT / "playbooks/storage_analysis.yml").read_text()
    play = yaml.safe_load(source.replace("/tmp/fleet_storage_report.json", str(tmp_path / "report.json")))[0]
    play["become"] = False
    play["environment"] = {"STORAGE_TEST_HOST": "{{ inventory_hostname }}"}
    play["vars"] = {"__fleet_scan_dir": str(tmp_path / "scans"), "__fleet_results_dir": str(tmp_path / "results")}
    result = run_playbook(tmp_path, play, str(inventory))
    output = result.stdout + result.stderr
    assert result.returncode == 2, output
    assert "Storage discovery command failed on broken" in output
    assert "rc: 42" in output
    assert "discovery stdout evidence" in output
    assert "discovery stderr evidence" in output
    for report in (tmp_path / "scans/storage_healthy.json", tmp_path / "results/manual/storage_healthy.json"):
        data = json.loads(report.read_text())
        assert data["hostname"] == "healthy"
        assert data["mounts"] == mounts
    assert not (tmp_path / "scans/storage_broken.json").exists()
    assert not (tmp_path / "report.json").exists()
