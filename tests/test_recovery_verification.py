"""Run the recovery playbook with isolated local files and a fake cluster API."""
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
@pytest.mark.parametrize("mode,local_member,prior_member,api,ready,health_ok,expected_rc", [
    ("unknown", False, False, "missing", True, True, 0),
    ("unknown", False, False, "unavailable", True, True, 0),
    ("standalone", False, False, "unavailable", True, True, 0),
    ("unknown", True, False, "found", True, True, 0),
    ("unknown", False, False, "found", True, True, 0),
    ("standalone", True, False, "found", True, True, 0),
    ("kubernetes", False, False, "found", True, True, 0),
    ("unknown", True, False, "unavailable", True, True, 2),
    ("unknown", True, False, "missing", True, True, 2),
    ("unknown", False, True, "unavailable", True, True, 2),
    ("kubernetes", False, False, "missing", True, True, 2),
    ("unknown", True, False, "ambiguous", True, True, 2),
    ("unknown", True, False, "found", False, True, 2),
    ("unknown", True, False, "found", True, False, 2),
    ("unknown", False, False, "missing", True, False, 2),
])
def test_recovery_uses_membership_without_requiring_maintenance_policy(
    tmp_path, mode, local_member, prior_member, api, ready, health_ok, expected_rc,
):
    playbooks = tmp_path / "playbooks"
    shutil.copytree(ROOT / "playbooks", playbooks)
    # Redirect only the membership file paths into the sandbox. Execute the
    # production stat, discovery, policy, and health tasks without SSH or sudo.
    indicator = tmp_path / "kubelet.conf"
    if local_member:
        indicator.touch()
    indicators_path = playbooks / "tasks/kubernetes_indicators.yml"
    indicators = yaml.safe_load(indicators_path.read_text())
    indicators[0]["loop"] = [str(indicator)]
    indicators_path.write_text(yaml.safe_dump(indicators))

    calls = tmp_path / "cluster-calls.jsonl"
    collection = tmp_path / "collections/ansible_collections/kubernetes/core/plugins/modules"
    collection.mkdir(parents=True)
    node = {
        "metadata": {"name": "test-node", "uid": "test-node-uid"},
        "spec": {"unschedulable": True},
        "status": {"conditions": [{"type": "Ready", "status": "True" if ready else "False"}]},
    }
    nodes = [node] if api in {"found", "ambiguous"} else []
    if api == "ambiguous":
        nodes.append({**node, "metadata": {"name": "TEST-NODE", "uid": "different-node"}})
    (collection / "k8s_info.py").write_text(
        "import json\nfrom ansible.module_utils.basic import AnsibleModule\n"
        "m = AnsibleModule(argument_spec={key: dict(type='str') for key in "
        "['api_version', 'kind', 'name', 'kubeconfig', 'context']})\n"
        f"with open({str(calls)!r}, 'a') as f: f.write(json.dumps(m.params) + '\\n')\n"
        f"if {api == 'unavailable'!r}: m.fail_json(msg='Test API is unavailable')\n"
        f"m.exit_json(changed=False, resources={nodes!r})\n"
    )
    mutations = tmp_path / "mutations"
    (collection / "k8s_drain.py").write_text(
        "from ansible.module_utils.basic import AnsibleModule\n"
        f"open({str(mutations)!r}, 'w').write('unexpected scheduling change')\n"
        "AnsibleModule(argument_spec={}).fail_json(msg='Recovery must never change scheduling')\n"
    )
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
            "fleet_kubernetes_membership_expected": prior_member,
            "kubernetes_ready_retries": 0, "kubernetes_ready_delay": 0,
        },
        "environment": {"PATH": f"{fakebin}:{os.environ.get('PATH', '')}"},
    })
    play[0]["post_tasks"] = [{
        "name": "Recovery preserves the saved maintenance policy",
        "ansible.builtin.assert": {"that": [f"fleet_maintenance_mode == '{mode}'"]},
    }]
    path.write_text(yaml.safe_dump(play))
    config = tmp_path / "ansible.cfg"
    config.write_text("[defaults]\nretry_files_enabled = False\n")
    result = subprocess.run(
        [ANSIBLE, "-i", "test-node,", str(path)], capture_output=True, text=True, timeout=40,
        env={**os.environ, "ANSIBLE_CONFIG": str(config), "ANSIBLE_NOCOLOR": "1",
             "ANSIBLE_COLLECTIONS_PATH": str(tmp_path / "collections")},
    )
    output = result.stdout + result.stderr
    assert result.returncode == expected_rc, output
    assert "changed=0" in output, output
    assert not mutations.exists(), output
    queries = [json.loads(line) for line in calls.read_text().splitlines()]
    if expected_rc == 0 and api == "found":
        assert any(query["name"] == "test-node" for query in queries), output
    if expected_rc == 2 and api in {"missing", "unavailable"} and health_ok:
        assert "Kubernetes membership is configured or detected" in output
    if expected_rc == 2 and api == "ambiguous":
        assert "Multiple nodes match this device" in output
