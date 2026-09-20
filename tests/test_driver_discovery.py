"""Exercise scan driver discovery without distribution Python APT bindings."""
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


@pytest.mark.skipif(not ANSIBLE, reason="ansible-playbook is required")
@pytest.mark.parametrize("family,packages,query_rc,expected", [
    ("Debian", "nvidia-driver-580 installed\n", 0, "nvidia-driver-580"),
    ("Debian", "nvidia-driver-580-server installed\n", 0, "nvidia-driver-580-server"),
    ("Debian", "nvidia-driver-580-open installed\n", 0, "nvidia-driver-580-open"),
    ("Debian", "nvidia-driver-580-server-open installed\n", 0, "nvidia-driver-580-server-open"),
    ("Debian", "nvidia-driver-535 config-files\nnvidia-driver-570 half-configured\nnvidia-driver-580-open installed\n", 0, "nvidia-driver-580-open"),
    ("Debian", "nvidia-l4t-core installed\nnvidia-driver-helper installed\n", 0, ""),
    ("Debian", "", 1, ""),  # Jetson uses L4T, with no desktop driver metapackage.
    ("RedHat", "", 0, ""),  # Do not require dpkg on other platforms.
    ("Debian", "", 2, None),  # Real database errors must still fail verification.
])
def test_driver_discovery_uses_native_package_database(tmp_path, family, packages, query_rc, expected):
    fakebin = tmp_path / "bin"
    fakebin.mkdir()
    invocation = tmp_path / "query.json"
    query = fakebin / "dpkg-query"
    query.write_text(
        f"#!{sys.executable}\n"
        "import json, pathlib, sys\n"
        f"pathlib.Path({str(invocation)!r}).write_text(json.dumps(sys.argv[1:]))\n"
        f"sys.stdout.write({packages!r})\n"
        f"sys.exit({query_rc})\n"
    )
    query.chmod(0o700)
    tasks = [{
        "name": "Run production driver discovery",
        "ansible.builtin.include_tasks": str(ROOT / "playbooks/tasks/discover_driver_package.yml"),
    }]
    if expected is not None:
        tasks.append({
            "name": "Verify driver eligibility evidence",
            "ansible.builtin.assert": {"that": ["fleet_nvidia_driver_package == expected_package"]},
        })
    play = [{
        "name": "Verify portable driver discovery",
        "hosts": "localhost", "connection": "local", "gather_facts": False,
        "vars": {
            "ansible_python_interpreter": sys.executable,
            "ansible_facts": {"os_family": family}, "expected_package": expected,
        },
        "environment": {"PATH": f"{fakebin}:{os.environ.get('PATH', '')}", "Package": "must-not-expand"},
        "tasks": tasks,
    }]
    path = tmp_path / "driver.yml"
    path.write_text(yaml.safe_dump(play))
    config = tmp_path / "ansible.cfg"
    config.write_text("[defaults]\n")
    result = subprocess.run(
        [ANSIBLE, "-i", "localhost,", str(path)], capture_output=True, text=True, timeout=20,
        env={**os.environ, "ANSIBLE_CONFIG": str(config)},
    )
    assert result.returncode == (2 if expected is None else 0), result.stdout + result.stderr
    if family == "Debian":
        assert json.loads(invocation.read_text()) == [
            "--show", "--showformat=${Package} ${db:Status-Status}\\n", "nvidia-driver-*",
        ]
    else:
        assert not invocation.exists()
