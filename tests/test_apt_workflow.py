"""Execute production apt tasks against fake CLIs; never touch host packages."""
import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parents[1]
ANSIBLE = shutil.which('ansible-playbook')
pytestmark = pytest.mark.skipif(not ANSIBLE, reason='ansible-playbook is required')


@pytest.fixture
def apt_host(tmp_path):
    bin_dir = tmp_path / 'bin'; bin_dir.mkdir()
    log = tmp_path / 'calls.jsonl'
    script = '''#!PYTHON
import json, pathlib, sys
name = pathlib.Path(sys.argv[0]).name
with open(LOG, 'a') as f: f.write(json.dumps([name, *sys.argv[1:]]) + '\\n')
if name == 'apt-get' and '--simulate' in sys.argv:
 print('Inst curl [1.0] (2.0 Ubuntu [amd64])')
 print('Inst libssl3:amd64 [3.0] (3.1 Ubuntu [amd64])')
 print('Conf curl (2.0 Ubuntu [amd64])')
elif name == 'dpkg-query':
 print({'curl':'2.0','libssl3:amd64':'3.1'}[sys.argv[-1]],end='')
'''.replace('PYTHON', sys.executable).replace('LOG', repr(str(log)))
    for command in ('apt-get','dpkg','dpkg-query'):
        path = bin_dir / command; path.write_text(script); path.chmod(0o755)
    tasks = tmp_path / 'tasks'; tasks.mkdir()
    for name in ('package_plan.yml','save_operation_report.yml'):
        shutil.copy(ROOT/'playbooks/tasks'/name, tasks/name)
    config = tmp_path / 'ansible.cfg'; config.write_text('[defaults]\nhost_key_checking=True\n')

    def run(name, values=None):
        document = yaml.safe_load((ROOT/'playbooks'/name).read_text())
        play = document[0]
        play.update(hosts='localhost', connection='local', become=False, gather_facts=False)
        play.setdefault('environment', {})['PATH'] = str(bin_dir) + os.pathsep + os.environ['PATH']
        job_id = str(uuid.uuid4())
        play['vars'] = {'ansible_python_interpreter':sys.executable, 'ansible_facts':{'os_family':'Debian'}, '__fleet_results_dir':str(tmp_path/'reports'), '__fleet_job_id':job_id, **(values or {})}
        fixture = tmp_path/name; fixture.write_text(yaml.safe_dump(document, sort_keys=False))
        result = subprocess.run([ANSIBLE,'-i','localhost,',str(fixture)],capture_output=True,text=True,timeout=45,env={**os.environ,'ANSIBLE_CONFIG':str(config)})
        return result, tmp_path/'reports'/job_id
    return run, log


@pytest.mark.parametrize('mode', ['unknown', 'standalone', 'kubernetes'])
def test_check_and_install_pin_versions_without_python_apt_or_cluster_access(apt_host, mode):
    run, log = apt_host
    result, directory = run('package_preview.yml')
    assert result.returncode == 0, result.stdout+result.stderr
    report = json.loads((directory/'packages_localhost.json').read_text())
    assert report['package_count'] == 2
    assert len(report['fingerprint']) == 64
    assert not any('install' in json.loads(line) for line in log.read_text().splitlines())
    result, directory = run('system_update.yml', {'fleet_approved_package_plans':{'localhost':report['fingerprint']}, 'fleet_maintenance_mode':mode, 'fleet_kubernetes_membership_expected':True, 'kubernetes_kubeconfig':'/missing-kubeconfig'})
    assert result.returncode == 0, result.stdout+result.stderr
    calls = [json.loads(line) for line in log.read_text().splitlines()]
    install = next(call for call in calls if 'install' in call)
    assert install[-2:] == ['curl=2.0','libssl3:amd64=3.1']
    assert '--no-remove' in install and '--no-install-recommends' in install
    assert json.loads((directory/'apt_install_localhost.json').read_text())['package_count'] == 2
    assert json.loads((directory/'execution_localhost.json').read_text())['mutation_started']


def test_drift_fails_before_mutation_marker_or_install(apt_host):
    run, log = apt_host
    result, directory = run('system_update.yml', {'fleet_approved_package_plans':{'localhost':'a'*64}})
    assert result.returncode != 0
    assert 'No packages were installed' in result.stdout
    assert not (directory/'execution_localhost.json').exists()
    assert not any('install' in json.loads(line) for line in log.read_text().splitlines())
