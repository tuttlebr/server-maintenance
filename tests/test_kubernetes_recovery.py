"""Execute the real scheduling task flow against a local fake Kubernetes API.

Only localhost is in inventory. Fake collection modules record intent in temp
files; no API, SSH endpoint, or managed service is contacted.
"""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parents[1]
ANSIBLE = shutil.which('ansible-playbook')


@pytest.mark.skipif(not ANSIBLE, reason='ansible-playbook is required for workflow integration tests')
@pytest.mark.parametrize('mode,drain_fails,maintenance_fails,ready,originally_cordoned,health_ok,expected_rc,actions', [
    ('unknown',False,False,True,False,True,2,[]),
    ('standalone',False,False,True,False,True,0,[]),
    ('kubernetes',True,False,True,False,True,2,['drain']),
    ('kubernetes',False,True,True,False,True,2,['drain']),
    ('kubernetes',False,False,False,False,True,2,['drain']),
    ('kubernetes',False,False,'pressure_unknown',False,True,2,['drain']),
    ('kubernetes',False,False,True,False,False,2,['drain']),
    ('kubernetes',False,False,True,True,True,0,['drain']),
    ('kubernetes',False,False,True,False,True,0,['drain','uncordon']),
])
def test_scheduling_recovery(tmp_path, mode, drain_fails, maintenance_fails, ready, originally_cordoned, health_ok, expected_rc, actions):
    collection = tmp_path/'collections/ansible_collections/kubernetes/core/plugins/modules'
    collection.mkdir(parents=True)
    action_log=tmp_path/'actions.jsonl'
    node={'metadata':{'name':'test-node','uid':'test-node-uid'},'spec':{'unschedulable':originally_cordoned},'status':{'conditions':[{'type':'Ready','status':'True' if ready else 'False'}]}}
    if ready == 'pressure_unknown': node['status']['conditions'].append({'type':'MemoryPressure','status':'Unknown'})
    (collection/'k8s_info.py').write_text('''from ansible.module_utils.basic import AnsibleModule
m=AnsibleModule(argument_spec={key:dict(type='str') for key in ['api_version','kind','name','kubeconfig','context']})
m.exit_json(changed=False,resources='''+repr([node])+')\n')
    (collection/'k8s_drain.py').write_text('''import json
from ansible.module_utils.basic import AnsibleModule
m=AnsibleModule(argument_spec={**{key:dict(type='str') for key in ['state','name','kubeconfig','context']},'delete_options':dict(type='dict')})
with open('''+repr(str(action_log))+''','a') as f: f.write(json.dumps(m.params)+'\\n')
if m.params['state']=='drain' and '''+repr(drain_fails)+''': m.fail_json(msg='Disruption budget blocked eviction')
m.exit_json(changed=True)
''')
    fakebin=tmp_path/'bin';fakebin.mkdir()
    fakeawk=fakebin/'awk'
    fakeawk.write_text('#!/bin/sh\nexit 0\n');fakeawk.chmod(0o700)
    findmnt=fakebin/'findmnt'
    findmnt.write_text('#!/bin/sh\nexit '+('0' if health_ok else '1')+'\n');findmnt.chmod(0o700)
    play = [{'name':'Exercise production Kubernetes task flow', 'hosts':'all', 'gather_facts':False,
        'vars': {'ansible_connection':'local','ansible_python_interpreter':shutil.which('python'),
                 'fleet_maintenance_mode':mode,'kubernetes_node_name':'test-node',
                 'ansible_facts':{'service_mgr':'test','os_family':'test'},
                 'kubernetes_ready_retries':1,'kubernetes_ready_delay':0},
        'environment':{'PATH':f'{fakebin}:{os.environ.get("PATH", "")}'},
        'tasks':[{'name':'Prepare maintenance','ansible.builtin.include_tasks':str(ROOT/'playbooks/tasks/kubernetes_prepare.yml')},
                 {'name':'Simulate requested maintenance failure','ansible.builtin.fail':{'msg':'Injected maintenance failure'},'when':maintenance_fails}],
        'handlers':[{'name':'Restore Kubernetes node scheduling','ansible.builtin.include_tasks':str(ROOT/'playbooks/tasks/kubernetes_restore.yml')}]}]
    (tmp_path/'ansible.cfg').write_text('[defaults]\nretry_files_enabled = False\n')
    playbook=tmp_path/'workflow.yml';playbook.write_text(yaml.safe_dump(play))
    result=subprocess.run([ANSIBLE,'-i','localhost,',str(playbook)],capture_output=True,text=True,timeout=40,
        env={**os.environ,'ANSIBLE_COLLECTIONS_PATH':str(tmp_path/'collections'),'ANSIBLE_CONFIG':str(tmp_path/'ansible.cfg'),'ANSIBLE_NOCOLOR':'1'})
    assert result.returncode == expected_rc, result.stdout+result.stderr
    recorded=[json.loads(line) for line in action_log.read_text().splitlines()] if action_log.exists() else []
    assert [action['state'] for action in recorded] == actions
    for action in recorded:
        assert action['name']=='test-node'
        if action['state']=='drain':
            assert action['delete_options']['disable_eviction'] is False
            assert action['delete_options']['force'] is False
            assert action['delete_options']['delete_emptydir_data'] is False


@pytest.mark.skipif(not ANSIBLE, reason='ansible-playbook is required for transaction parsing tests')
@pytest.mark.parametrize('family,plan,expected', [
    ('Debian',['Inst openssl [3.0.1] (3.0.2 Ubuntu [amd64])', 'Conf openssl (3.0.2 Ubuntu [amd64])','Inst linux-image-generic (6.8.0 Ubuntu [amd64])'],['linux-image-generic=6.8.0','openssl=3.0.2']),
    ('RedHat',['Installed: openssl-1:3.0.2-1.el9.x86_64','Removed: openssl-1:3.0.1-1.el9.x86_64'],['openssl-1:3.0.2-1.el9.x86_64']),
    ('Debian',[],[]),
])
def test_preview_pins_exact_versions(tmp_path, family, plan, expected):
    tasks=yaml.safe_load((ROOT/'playbooks/tasks/package_plan.yml').read_text())
    tasks=[task for task in tasks if 'ansible.builtin.set_fact' in task]
    tasks.append({'name':'Assert reviewed versions','ansible.builtin.assert':{'that':['fleet_package_targets == expected_packages', 'fleet_package_fingerprint | length == 64']}})
    play=[{'name':'Test package plan parsing','hosts':'localhost','connection':'local','gather_facts':False,
           'vars':{'ansible_facts':{'os_family':family},'fleet_apt_plan':{'stdout_lines':plan},'fleet_dnf_plan':{'results':plan},'expected_packages':expected},'tasks':tasks}]
    path=tmp_path/'packages.yml';path.write_text(yaml.safe_dump(play))
    (tmp_path/'ansible.cfg').write_text('[defaults]\n')
    result=subprocess.run([ANSIBLE,'-i','localhost,',str(path)],capture_output=True,text=True,timeout=15,env={**os.environ,'ANSIBLE_CONFIG':str(tmp_path/'ansible.cfg')})
    assert result.returncode==0, result.stdout+result.stderr
