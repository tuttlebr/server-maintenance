"""Legacy false locks clear from positive evidence, never just elapsed time."""
import json
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.capabilities import OPERATION_BY_ID, operation_ineligibility
from backend.database import Base
from backend.models import Device, DeviceReservation, Job
from backend.services import recovery_state
from backend.services.execution_state import reconcile_interrupted_jobs


def preflight_log(name='node-01', failure='Require a matching reviewed package preview'):
    return f'''PLAY [Update System Packages] ************************
TASK [Gathering Facts] ************************
ok: [{name}]
TASK [Validate supported package manager] ************************
ok: [{name}] => {{"changed": false}}
TASK [{failure}] ************************
fatal: [{name}]: FAILED! => {{"changed": false, "msg": "Package changes differ from the reviewed preview."}}
PLAY RECAP ************************
{name} : ok=2 changed=0 unreachable=0 failed=1 skipped=0 rescued=0 ignored=0
'''


@pytest.fixture
def state(tmp_path, monkeypatch):
    monkeypatch.setattr(recovery_state, 'get_job_results', lambda job_id: [])
    engine = create_engine(f'sqlite:///{tmp_path}/fleet.db')
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        job = Job(job_id=str(uuid.uuid4()), playbook='system_update.yml',
                  target_hosts='node-01', status='recovery_required', phase='complete',
                  execution_kind='mutation', finished_at=datetime.now(timezone.utc),
                  output_log=preflight_log(), outcomes_json=json.dumps([{'hostname':'node-01','status':'failed'}]))
        host = Device(hostname='node-01', recovery_required=True, facts_stale=True,
                      recovery_reason=f'Incomplete job {job.job_id} ({job.playbook})',
                      transport='ssh', os_family='Debian', maintenance_mode='standalone')
        host.capabilities = ['system.update', 'containers.cleanup']
        db.add_all([job, host]); db.commit()
        yield db, job, host
    engine.dispose()


def test_startup_repairs_legacy_preflight_without_running_a_remote_check(state):
    db, job, host = state
    log = job.output_log
    reconcile_interrupted_jobs(db)
    assert recovery_state.reconcile_stale_recovery(db) == ['node-01']
    assert not host.recovery_required and host.recovery_reason is None
    assert host.facts_stale  # Clearing a false lock doesn't invent fresh facts.
    assert job.status == 'failed' and job.output_log == log
    assert 'before any device changes' in job.device_results[0]['recovery_resolution']
    assert 'Scan devices first' in operation_ineligibility(host, OPERATION_BY_ID['system.update'])
    assert recovery_state.reconcile_stale_recovery(db) == []


def test_serial_targets_never_reached_are_unblocked_too(state):
    db, job, host = state
    job.target_hosts = 'node-01,node-02'
    second = Device(hostname='node-02', recovery_required=True, recovery_reason=host.recovery_reason)
    db.add(second); db.commit()
    assert set(recovery_state.reconcile_stale_recovery(db)) == {'node-01','node-02'}
    assert not second.recovery_required
    assert 'before reaching' in job.device_results[1]['recovery_resolution']
    assert job.status == 'failed'


def test_ssh_failure_before_facts_is_not_a_recovery_event(state):
    db, job, host = state
    job.output_log = '''PLAY [Update System Packages] ************************
TASK [Gathering Facts] ************************
fatal: [node-01]: UNREACHABLE! => {"changed": false, "msg": "Connection refused"}
PLAY RECAP ************************
node-01 : ok=0 changed=0 unreachable=1 failed=0 skipped=0 rescued=0 ignored=0
'''
    db.commit()
    assert recovery_state.reconcile_stale_recovery(db) == ['node-01']


@pytest.mark.parametrize('case', ['drain', 'late_drift', 'unknown_task', 'changed', 'missing_log',
                                'truncated_log', 'missing_start', 'timeout', 'interrupted',
                                'unknown_source', 'other_job', 'wrong_playbook', 'active', 'reserved'])
def test_uncertain_or_real_changes_keep_recovery(state, case):
    db, job, host = state
    if case == 'drain': job.output_log = preflight_log(failure='Drain while respecting disruption budgets')
    if case == 'late_drift': job.output_log = preflight_log(failure='Require the approved plan immediately before applying it')
    if case == 'unknown_task': job.output_log = job.output_log.replace('TASK [Require', 'TASK [Unexpected mutation] ********\nok: [node-01]\nTASK [Require', 1)
    if case == 'changed': job.output_log = job.output_log.replace('changed=0', 'changed=1')
    if case == 'missing_log': job.output_log = ''
    if case == 'truncated_log': job.output_log = job.output_log.partition('PLAY RECAP')[0]
    if case == 'missing_start': job.output_log = job.output_log.partition('TASK [Validate')[2]
    if case == 'timeout': job.error_summary = 'Timed out after 3600 seconds.'
    if case == 'interrupted': job.phase = 'interrupted'
    if case == 'unknown_source': host.recovery_reason = 'Manual recovery required'
    if case == 'other_job': host.recovery_reason = f'Incomplete job {uuid.uuid4()} ({job.playbook})'
    if case == 'wrong_playbook': job.playbook = 'reboot.yml'
    if case == 'active': db.add(Job(job_id=str(uuid.uuid4()), playbook='host_facts.yml', target_hosts=host.hostname, status='running'))
    if case == 'reserved': db.add(DeviceReservation(device_id=host.id, job_id=job.job_id))
    db.commit()
    assert recovery_state.reconcile_stale_recovery(db) == []
    assert host.recovery_required and host.recovery_reason
    assert job.status == 'recovery_required'


@pytest.mark.parametrize('report_type', ['execution', 'kubernetes', 'apt_install', 'cleanup'])
def test_mutation_artifacts_override_preflight_log_inference(state, monkeypatch, report_type):
    db, job, host = state
    monkeypatch.setattr(recovery_state, 'get_job_results', lambda job_id: [{'hostname':host.hostname,'report_type':report_type,'mutation_started':True}])
    assert recovery_state.reconcile_stale_recovery(db) == []
    assert host.recovery_required


def test_one_preflight_failure_cannot_clear_another_hosts_failed_drain(state):
    db, job, host = state
    job.target_hosts = 'node-01,node-02,node-03'
    job.output_log = (preflight_log().partition('PLAY RECAP')[0]
                      + preflight_log('node-02', 'Drain while respecting disruption budgets').replace(
                          'PLAY RECAP ************************', 'PLAY RECAP ************************\nnode-01 : ok=2 changed=0 unreachable=0 failed=1'))
    db.add_all([Device(hostname=name, recovery_required=True, recovery_reason=host.recovery_reason)
                for name in ['node-02','node-03']]); db.commit()
    assert recovery_state.reconcile_stale_recovery(db) == ['node-01']
    assert job.status == 'recovery_required'
    assert all(item.recovery_required for item in db.query(Device).filter(Device.hostname != 'node-01'))


def test_unavailable_container_runtime_before_prune_clears_legacy_flag(state):
    db, job, host = state
    job.playbook = 'docker_cleanup.yml'
    host.recovery_reason = f'Incomplete job {job.job_id} ({job.playbook})'
    job.output_log = preflight_log(failure='Require at least one available container runtime').replace(
        'Gathering Facts', 'Check if Docker CLI is installed').replace('Validate supported package manager', 'Check whether Docker is running')
    db.commit()
    assert recovery_state.reconcile_stale_recovery(db) == ['node-01']
