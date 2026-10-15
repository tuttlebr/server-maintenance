"""Execute production account loops/preflight with all OS-changing modules faked."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT=Path(__file__).parents[1]
ANSIBLE=shutil.which('ansible-playbook')
pytestmark=pytest.mark.skipif(not ANSIBLE,reason='ansible-playbook required')


@pytest.fixture
def accounts(tmp_path):
    library=tmp_path/'library';library.mkdir()
    calls=tmp_path/'calls.jsonl'
    (library/'fake_account_change.py').write_text('''import json
from pathlib import Path
from ansible.module_utils.basic import AnsibleModule
m=AnsibleModule(argument_spec={key:dict(type='raw') for key in ['name','comment','groups','append','shell','state','create_home','password','update_password','calls','kind','marker','path','line','create','owner','group','mode','validate']})
assert json.loads(Path(m.params['marker']).read_text())['mutation_started']
with open(m.params['calls'],'a') as f:f.write(json.dumps(m.params)+'\\n')
m.exit_json(changed=True)
''')
    tasks=tmp_path/'tasks';tasks.mkdir()
    shutil.copy(ROOT/'playbooks/tasks/save_operation_report.yml',tasks)
    (tasks/'account_report.yml').write_text('- name: Fake read-only observations\n  ansible.builtin.debug:\n    msg: "{{ fleet_account_names }}"\n')
    def run(values):
        play=yaml.safe_load((ROOT/'playbooks/user_management.yml').read_text())[0]
        play.update(hosts='localhost',connection='local',become=False,gather_facts=False)
        missing_visudo=values.pop('test_missing_visudo',False)
        play['vars'].update({'ansible_python_interpreter':sys.executable,'ansible_user':'admin','ansible_facts':{'os_family':'Debian'},'__fleet_results_dir':str(tmp_path/'reports'),'__fleet_job_id':'job',**values})
        for task in play['tasks']:
            if task['name']=='Require sudo policy validation before granting access':
                task['ansible.builtin.command']['argv']=['test','-x','/nonexistent/visudo' if missing_visudo else sys.executable]
            if 'ansible.builtin.getent' in task:
                task.pop('ansible.builtin.getent');task['ansible.builtin.set_fact']={'ansible_facts':{'getent_passwd':{'jane':['x','1001','1001','Old Name','/home/jane','/bin/sh']},'os_family':'Debian'}}
            for module in ['user','group','file','lineinfile']:
                if f'ansible.builtin.{module}' in task:
                    task['fake_account_change']=task.pop(f'ansible.builtin.{module}')
                    task['fake_account_change'].update(kind=module,calls=str(calls),marker=str(tmp_path/'reports/job/execution_localhost.json'))
        path=tmp_path/'users.yml';path.write_text(yaml.safe_dump([play],sort_keys=False))
        config=tmp_path/'ansible.cfg';config.write_text('[defaults]\n')
        result=subprocess.run([ANSIBLE,'-i','localhost,',str(path)],capture_output=True,text=True,timeout=45,env={**os.environ,'ANSIBLE_CONFIG':str(config),'ANSIBLE_LIBRARY':str(library)})
        return result,[json.loads(line) for line in calls.read_text().splitlines()] if calls.exists() else []
    return run,tmp_path/'reports/job/execution_localhost.json'


def test_add_preserves_existing_accounts_and_applies_new_user_fields(accounts):
    run,_=accounts
    result,calls=run({'user_records':[dict(username='jane',full_name='Unchanged',groups='ignored'),dict(username='sam',full_name='Sam',groups='dev,docker',shell='/bin/sh')]})
    assert result.returncode==0,result.stdout+result.stderr
    assert [c['name'] for c in calls if c['kind']=='group']==['dev','docker']
    added=[c for c in calls if c['kind']=='user']
    assert len(added)==1 and added[0]['name']=='sam'
    assert added[0]['shell']=='/bin/sh' and added[0]['comment']=='Sam'
    assert added[0]['groups']=='dev,docker' and added[0]['append'] is True
    assert added[0]['password'] is None


def test_edit_changes_only_supplied_fields_and_never_replaces_memberships(accounts):
    run,_=accounts
    result,calls=run({'user_updates':[dict(username='jane',groups='dev',full_name='Jane Updated')]})
    assert result.returncode==0,result.stdout+result.stderr
    changed=next(c for c in calls if c['kind']=='user')
    assert changed['name']=='jane' and changed['comment']=='Jane Updated'
    assert changed['groups']=='dev' and changed['append'] is True
    assert changed['shell'] is None and changed['password'] is None and changed['create_home'] is None


@pytest.mark.parametrize('record',[dict(username='missing',groups='dev'),dict(username='root',groups='dev'),dict(username='admin',groups='dev'),dict(username='jane',shell='/nonexistent/shell')])
def test_preflight_failure_never_starts_account_mutations(accounts,record):
    run,marker=accounts
    result,calls=run({'user_updates':[record]})
    assert result.returncode!=0
    assert calls==[]
    assert not marker.exists()


def test_sudo_grants_apply_only_to_opted_in_new_accounts(accounts):
    run,_=accounts
    result,calls=run({'user_records':[
        dict(username='jane',full_name='Existing',grant_sudo=True),
        dict(username='sam',full_name='Sam',grant_sudo=True),
        dict(username='alice',full_name='Alice',grant_sudo=False),
        dict(username='bob',full_name='Bob'),
    ]})
    assert result.returncode==0,result.stdout+result.stderr
    grants=[c for c in calls if c['kind']=='lineinfile']
    assert len(grants)==1
    assert grants[0]['path']=='/etc/sudoers.d/sam'
    assert grants[0]['line']=='sam ALL=(ALL) NOPASSWD:ALL'
    assert grants[0]['mode']=='0440' and grants[0]['owner']=='root'
    assert grants[0]['validate']=='/usr/sbin/visudo -cf %s'
    assert grants[0]['state']=='present'


def test_sudo_only_edit_grants_access_without_replacing_account_fields(accounts):
    run,_=accounts
    result,calls=run({'user_updates':[dict(username='jane',grant_sudo=True)]})
    assert result.returncode==0,result.stdout+result.stderr
    grant=next(c for c in calls if c['kind']=='lineinfile')
    assert grant['path']=='/etc/sudoers.d/jane'
    changed=next(c for c in calls if c['kind']=='user')
    assert changed['groups'] is None and changed['shell'] is None


def test_unchecked_sudo_never_modifies_sudo_policy(accounts):
    run,_=accounts
    result,calls=run({'user_updates':[dict(username='jane',full_name='Jane',grant_sudo=False)]})
    assert result.returncode==0,result.stdout+result.stderr
    assert not any(c['kind'] in {'lineinfile','file'} for c in calls)


def test_missing_visudo_blocks_every_account_change(accounts):
    run,marker=accounts
    result,calls=run({'test_missing_visudo':True,'user_records':[dict(username='sam',full_name='Sam',grant_sudo=True)]})
    assert result.returncode!=0
    assert calls==[] and not marker.exists()
