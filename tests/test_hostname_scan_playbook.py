"""Exercise serial collection and report rendering with real Ansible tasks."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest
import yaml

from backend.models import Device
from backend.services.device_discovery import enrich_from_scan


ROOT = Path(__file__).parents[1]
ANSIBLE = shutil.which("ansible-playbook")
pytestmark = pytest.mark.skipif(not ANSIBLE, reason="ansible-playbook is required")


@pytest.mark.parametrize("case", ["jetson", "missing_files", "dmi"])
def test_scan_serial_collection_survives_optional_files(tmp_path, case):
    tasks = yaml.safe_load((ROOT / "playbooks/host_facts.yml").read_text())[0]["tasks"]
    reads = [task for task in tasks if task.get("register") in {"device_tree_model", "device_tree_serial"}]
    for task in reads:
        # Only redirect the hardware path. Keep the production command and its conditions.
        argv = task["ansible.builtin.command"]["argv"]
        path = tmp_path / Path(argv[-1]).name
        argv[-1] = str(path)
        if case == "jetson":
            path.write_bytes(b"NVIDIA Jetson AGX Orin\x00" if path.name == "model" else b"123456007890\x00")
    report_template = next(task["set_fact"]["host_report"] for task in tasks if task["name"] == "Compile host facts")
    fields = {key: report_template[key] for key in (
        "hostname", "architecture", "product_name", "motherboard_serial", "device_tree_model", "device_tree_serial",
    )}
    output_path = tmp_path / "report.json"
    play = [{"name": "Hostname scan fixture", "hosts": "localhost", "connection": "local", "gather_facts": False,
             "vars": {"ansible_python_interpreter": sys.executable, "ansible_facts": {
                 "architecture": "x86_64" if case == "dmi" else "aarch64",
                 "product_name": "DGX H100" if case == "dmi" else "NA",
                 "board_serial": "BOARD0123456" if case == "dmi" else "NA",
             }},
             "tasks": reads + [{"ansible.builtin.copy": {
                 "dest": str(output_path), "content": "{{ fixture_report | to_json }}", "mode": "0600",
             }, "vars": {"fixture_report": fields}}]}]
    playbook = tmp_path / "scan.yml"
    playbook.write_text(yaml.safe_dump(play))
    config = tmp_path / "ansible.cfg"
    config.write_text("[defaults]\nretry_files_enabled = False\n")
    result = subprocess.run(
        [ANSIBLE, "-i", "localhost,", str(playbook)], capture_output=True, text=True, timeout=30,
        env={**os.environ, "ANSIBLE_CONFIG": str(config), "ANSIBLE_NOCOLOR": "1"},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(output_path.read_text())
    device = Device(hostname="localhost", kind="generic")
    enrich_from_scan(device, report)
    if case == "jetson":
        assert device.facts["recommended_hostname"] == "ai-sae-jetson-007890"
        assert device.facts["device_tree"]["serial"] == "123456007890"
    elif case == "dmi":
        assert device.facts["recommended_hostname"] == "ai-sae-dgx-123456"
        assert report["device_tree_serial"] == ""
    else:
        assert device.facts["recommended_hostname"] is None
        assert report["device_tree_model"] == ""
        assert report["device_tree_serial"] == ""
