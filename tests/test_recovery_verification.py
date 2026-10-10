"""Recovery verifies host health without cluster access or scheduling changes."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parents[1]
ANSIBLE = shutil.which("ansible-playbook")


@pytest.mark.skipif(not ANSIBLE, reason="ansible-playbook is required")
@pytest.mark.parametrize("mode", ["unknown", "standalone", "kubernetes"])
@pytest.mark.parametrize("health_ok", [True, False])
def test_recovery_treats_all_hosts_as_standalone(tmp_path, mode, health_ok):
    playbooks = tmp_path / "playbooks"
    shutil.copytree(ROOT / "playbooks", playbooks)
    # No Kubernetes tasks are available. A reintroduced dependency must fail,
    # including when inventory still contains cluster membership and settings.
    for task in (playbooks / "tasks").glob("kubernetes_*.yml"):
        task.unlink()
    fakebin = tmp_path / "bin"
    fakebin.mkdir()
    for command in ("awk", "findmnt"):
        executable = fakebin / command
        executable.write_text(f"#!/bin/sh\nexit {1 if command == 'findmnt' and not health_ok else 0}\n")
        executable.chmod(0o700)

    path = playbooks / "recovery_check.yml"
    play = yaml.safe_load(path.read_text())
    play[0].update({
        "hosts": "test-node", "connection": "local", "gather_facts": False, "become": False,
        "vars": {
            "ansible_python_interpreter": sys.executable,
            "ansible_facts": {"service_mgr": "test", "os_family": "test"},
            "fleet_maintenance_mode": mode,
            "fleet_kubernetes_membership_expected": True,
            "kubernetes_membership_expected": True,
            "kubernetes_kubeconfig": "/missing-kubeconfig",
        },
        "environment": {"PATH": f"{fakebin}:{os.environ.get('PATH', '')}"},
    })
    path.write_text(yaml.safe_dump(play))
    config = tmp_path / "ansible.cfg"
    config.write_text("[defaults]\nretry_files_enabled = False\n")
    result = subprocess.run(
        [ANSIBLE, "-i", "test-node,", str(path)], capture_output=True, text=True, timeout=40,
        env={**os.environ, "ANSIBLE_CONFIG": str(config), "ANSIBLE_NOCOLOR": "1"},
    )
    output = result.stdout + result.stderr
    assert result.returncode == (0 if health_ok else 2), output
    assert "changed=0" in output, output
    assert "Verify filesystem configuration" in output
    assert "kubernetes" not in output.lower(), output
