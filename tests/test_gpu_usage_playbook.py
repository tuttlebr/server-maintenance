"""Execute the GPU play against local fixture hosts, without touching GPUs."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest
import yaml


ROOT = Path(__file__).parents[1]
ANSIBLE = shutil.which('ansible-playbook')
pytestmark = pytest.mark.skipif(not ANSIBLE, reason='ansible-playbook is required')


def test_gpu_failure_preserves_other_nodes_report(tmp_path):
    binary = tmp_path / 'bin'; binary.mkdir()
    smi = binary / 'nvidia-smi'
    smi.write_text('#!'+sys.executable+'\nimport os, sys\n'
                   'if os.environ["GPU_TEST_HOST"] == "broken":\n'
                   '    sys.stderr.write("NVIDIA driver unavailable fixture")\n'
                   '    sys.exit(9)\n'
                   'print("<nvidia_smi_log><gpu><uuid>GPU-fixture</uuid><product_name>Test GPU</product_name><utilization><gpu_util>0 %</gpu_util></utilization><processes/></gpu></nvidia_smi_log>")\n')
    smi.chmod(0o755)
    (tmp_path / 'files').mkdir()
    shutil.copy(ROOT / 'playbooks/files/gpu_usage.py', tmp_path / 'files')
    inventory = tmp_path / 'inventory.yml'
    inventory.write_text(yaml.safe_dump({'all': {'children': {'gpu': {'hosts': {'healthy': {}, 'broken': {}}}}}}))
    source = (ROOT / 'playbooks/gpu_usage.yml').read_text()
    play = yaml.safe_load(source.replace('/tmp/fleet_gpu_usage_report.json', str(tmp_path / 'report_{{ inventory_hostname }}.json')))[0]
    play.update(connection='local', become=False)
    play['vars'] = {'ansible_python_interpreter': sys.executable, '__fleet_scan_dir': str(tmp_path / 'scans'), '__fleet_results_dir': str(tmp_path / 'results')}
    play['environment'] = {'PATH': str(binary)+':'+os.environ['PATH'], 'GPU_TEST_HOST': '{{ inventory_hostname }}'}
    path = tmp_path / 'play.yml'; path.write_text(yaml.safe_dump([play]))
    config = tmp_path / 'ansible.cfg'; config.write_text('[defaults]\nretry_files_enabled = False\n')
    result = subprocess.run([ANSIBLE, '-i', str(inventory), str(path)], capture_output=True, text=True, timeout=30,
                            env={**os.environ, 'ANSIBLE_CONFIG': str(config), 'ANSIBLE_NOCOLOR': '1'})
    assert result.returncode == 2, result.stdout + result.stderr
    assert 'NVIDIA driver unavailable fixture' in result.stdout
    for name in ['scans/gpu_usage_healthy.json', 'results/manual/gpu_healthy.json']:
        report = json.loads((tmp_path / name).read_text())
        assert report['hostname'] == 'healthy'
        assert report['gpus'][0]['utilization_pct'] == 0
        assert report['gpus'][0]['memory_used_mb'] is None
    assert not (tmp_path / 'results/manual/gpu_broken.json').exists()
    assert not (tmp_path / 'report_healthy.json').exists()
