"""Exercise the maintenance play headers on local inventory aliases."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml


PLAYBOOKS = Path(__file__).resolve().parents[1] / "playbooks"
ANSIBLE = shutil.which("ansible-playbook")


@pytest.mark.skipif(not ANSIBLE, reason="ansible-playbook is required")
@pytest.mark.parametrize("batch_size", [None, 1])
def test_maintenance_host_batches(tmp_path, batch_size):
    hosts = ["node-a", "node-b", "node-c"]
    inventory = tmp_path / "inventory.yml"
    groups = {}
    plays = []
    for name in (
        "system_update", "reboot", "service_control", "install_docker", "driver_upgrade",
        "firmware_update", "fabric_manager", "mig_management", "host_drain", "reachy_app_reset",
    ):
        header = yaml.safe_load((PLAYBOOKS / f"{name}.yml").read_text())[0]
        groups[header["hosts"]] = {"hosts": dict.fromkeys(hosts + ["unselected"], {})}
        plays.append({
            **{k: header[k] for k in ("name", "hosts", "serial", "strategy") if k in header},
            "gather_facts": False,
            "tasks": [{"ansible.builtin.assert": {
                "that": [f"ansible_play_batch | length == {batch_size or len(hosts)}"],
            }}],
        })
    inventory.write_text(yaml.safe_dump({"all": {"children": groups}}))
    playbook = tmp_path / "batches.yml"
    playbook.write_text(yaml.safe_dump(plays))
    cmd = [ANSIBLE, "-i", str(inventory), "--connection", "local", "--limit", ",".join(hosts), str(playbook)]
    if batch_size is not None:
        cmd.extend(["-e", f"maintenance_batch_size={batch_size}"])
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=40, env={**os.environ, "ANSIBLE_NOCOLOR": "1"})
    assert result.returncode == 0, result.stdout + result.stderr
    assert all(f"ok: [{host}]" in result.stdout for host in hosts)
