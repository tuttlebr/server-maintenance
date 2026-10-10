"""Run the production reboot flow with only the reboot action replaced by a fake.

No real reboot, SSH session, or service change is performed.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parents[1]
ANSIBLE = shutil.which('ansible-playbook')
pytestmark = pytest.mark.skipif(not ANSIBLE, reason='ansible-playbook is required')


@pytest.mark.parametrize('mode,reboot_required,result', [
    ('unknown', False, 'success'), ('standalone', True, 'success'),
    ('kubernetes', False, 'success'), ('standalone', False, 'failed'),
    ('standalone', False, 'not_rebooted'),
])
def test_reboot_is_unconditional_and_reports_only_a_confirmed_return(tmp_path, mode, reboot_required, result):
    library = tmp_path / 'library'; library.mkdir()
    calls = tmp_path / 'reboot-calls.jsonl'
    (library / 'fake_reboot.py').write_text('''import json
from pathlib import Path
from ansible.module_utils.basic import AnsibleModule
m = AnsibleModule(argument_spec={
    'msg':dict(type='str'), 'reboot_timeout':dict(type='int'),
    'connect_timeout':dict(type='int'), 'pre_reboot_delay':dict(type='int'),
    'post_reboot_delay':dict(type='int'), 'node':dict(type='str'),
    'results':dict(type='str'), 'result':dict(type='str'), 'calls':dict(type='str')})
marker = Path(m.params['results']) / ('execution_' + m.params['node'] + '.json')
if not json.loads(marker.read_text())['mutation_started']:
    m.fail_json(msg='Missing execution marker')
with open(m.params['calls'], 'a') as stream:
    stream.write(json.dumps(m.params) + '\\n')
if m.params['result'] == 'failed':
    m.fail_json(msg='Timed out waiting for SSH to return', changed=True)
m.exit_json(changed=True, rebooted=m.params['result'] != 'not_rebooted', elapsed=45)
''')
    tasks = tmp_path / 'tasks'; tasks.mkdir()
    shutil.copy(ROOT / 'playbooks/tasks/save_operation_report.yml', tasks)
    play = yaml.safe_load((ROOT / 'playbooks/reboot.yml').read_text())[0]
    assert play['gather_facts'] is False
    reboot = next(task for task in play['tasks'] if 'ansible.builtin.reboot' in task)
    # Replace just the real reboot action; execute every surrounding task and
    # condition from production, with no Kubernetes or health-check tasks present.
    reboot['fake_reboot'] = reboot.pop('ansible.builtin.reboot')
    reboot['fake_reboot'].update(node='{{ inventory_hostname }}', results=str(tmp_path / 'reports/job'), result=result, calls=str(calls))
    play.update(hosts='all', connection='local', become=False)
    play['vars'] = {
        'ansible_python_interpreter': sys.executable, '__fleet_results_dir': str(tmp_path / 'reports'),
        '__fleet_job_id': 'job', 'fleet_maintenance_mode': mode,
        'fleet_kubernetes_membership_expected': True, 'kubernetes_kubeconfig': '/missing-kubeconfig',
        'reboot_required': reboot_required, 'recovery_required': True, 'force_reboot': False,
    }
    path = tmp_path / 'reboot.yml'; path.write_text(yaml.safe_dump([play]))
    config = tmp_path / 'ansible.cfg'; config.write_text('[defaults]\n')
    run = subprocess.run([ANSIBLE, '-i', 'node-one,node-two,', str(path)], capture_output=True, text=True, timeout=30,
                         env={**os.environ, 'ANSIBLE_CONFIG': str(config), 'ANSIBLE_LIBRARY': str(library)})
    output = run.stdout + run.stderr
    assert run.returncode == (0 if result == 'success' else 2), output
    recorded = [json.loads(line) for line in calls.read_text().splitlines()]
    assert recorded[0]['node'] == 'node-one'
    assert recorded[0]['pre_reboot_delay'] == 0
    report = tmp_path / 'reports/job/reboot_node-one.json'
    if result == 'success':
        assert [call['node'] for call in recorded] == ['node-one', 'node-two']
        assert json.loads(report.read_text()) == {
            'schema_version': 1, 'report_type': 'reboot', 'hostname': 'node-one',
            'rebooted': True, 'elapsed_seconds': 45,
        }
    else:
        assert not report.exists()
