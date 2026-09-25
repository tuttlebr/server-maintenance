import asyncio
import json
import os
import signal
import subprocess
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from alembic import command
from alembic.config import Config
from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from backend.capabilities import OPERATION_BY_ID, operation_ineligibility
from backend.database import Base
from backend.models import Device, DeviceReservation, Job, ManagedUser, UserHostAssociation
from backend.routers.jobs import cancel_job_output
from backend.routers.operations import _approved_package_plans, run_operation
from backend.routers.users import _target_devices, _user_to_response, bulk_password_reset
from backend.schemas import BulkPasswordResetRequest, OperationRunRequest, SudoersRequest
from backend.services import ansible_runner as runner
from backend.services.account_state import reconcile_accounts
from backend.services.execution_state import ExecutionConflict, parse_host_outcomes, reconcile_interrupted_jobs, reserve_devices


@pytest.fixture
def database(tmp_path, monkeypatch):
    engine = create_engine(f'sqlite:///{tmp_path}/test.db', connect_args={'check_same_thread': False})
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    monkeypatch.setattr(runner, 'SessionLocal', sessions)
    monkeypatch.setattr(runner.settings, 'data_dir', tmp_path)
    monkeypatch.setattr(runner, 'regenerate_inventory', lambda db: None)
    monkeypatch.setattr(runner.job_log_indexer, 'ingest_completed_job', lambda job_id: None)
    monkeypatch.setattr(runner, '_JOB_SEMAPHORE', None)
    yield sessions
    engine.dispose()


def device(name='node-01', **values):
    item = Device(hostname=name, transport='ssh', maintenance_mode='standalone', os_family='Debian',
                  facts_stale=False, discovered_at=datetime.now(timezone.utc), **values)
    item.capabilities = [op.required_capability for op in OPERATION_BY_ID.values()]
    item.facts = {'distribution': 'Ubuntu', 'service_manager': 'systemd', 'nvidia_driver_package': 'nvidia-driver-580-open'}
    return item


def job(**values):
    return Job(job_id=str(uuid.uuid4()), playbook='system_update.yml', target_hosts='node-01', execution_kind='mutation', **values)


def test_restart_reconciliation_never_replays_and_marks_uncertain_state(database):
    with database() as db:
        host = device()
        db.add(host)
        db.flush()
        pending, running, read = job(status='pending'), job(status='running'), job(status='running')
        read.execution_kind = 'read_only'
        db.add_all([pending, running, read])
        db.flush()
        db.add(DeviceReservation(device_id=host.id, job_id=running.job_id))
        db.commit()
        reconcile_interrupted_jobs(db)
        assert pending.status == 'cancelled'
        assert running.status == 'recovery_required'
        assert read.status == 'failed'
        assert host.facts_stale and host.recovery_required
        assert db.query(DeviceReservation).count() == 0
        assert 'No automatic replay' in pending.error_summary
        reconcile_interrupted_jobs(db)
        assert running.status == 'recovery_required'


def test_reservations_reject_overlap_and_recovery_mutations(database):
    with database() as db:
        host = device()
        db.add(host)
        db.commit()
        first = job(status='pending')
        reserve_devices(db, first, [host])
        with pytest.raises(ExecutionConflict, match='reserved'):
            reserve_devices(db, job(status='pending'), [host])
        assert db.query(Job).count() == 1
        db.query(DeviceReservation).delete()
        host.recovery_required = True
        db.commit()
        with pytest.raises(ExecutionConflict, match='recovery'):
            reserve_devices(db, job(status='pending'), [host])


def test_explicit_account_scope_and_no_global_privilege_claim(database):
    with database() as db:
        db.add(device())
        user = ManagedUser(username='operator', is_sudoer=True, groups='sudo')
        db.add(user)
        db.commit()
        with pytest.raises(HTTPException, match='explicit'):
            _target_devices(SudoersRequest(all_devices=True), db)
        response = _user_to_response(db, user)
        assert 'is_sudoer' not in response and 'groups' not in response
        assert response['placements'] == []
        with pytest.raises(HTTPException, match='explicit account'):
            asyncio.run(bulk_password_reset(BulkPasswordResetRequest(device_ids=[1], temp_password='long-random-test-password'), db, 'test'))


def test_account_observations_preserve_host_specific_groups_and_sudo(database):
    with database() as db:
        db.add_all([device('node-01'), device('node-02')])
        db.commit()
        reports = [dict(report_type='accounts', hostname=host, accounts=[dict(username='operator', present=True, groups=groups, shell='/bin/bash', managed_sudo=sudo, sudo_policy='evidence')]) for host, groups, sudo in [('node-01', ['users','docker'],True), ('node-02', ['users','sudo'],False)]]
        reconcile_accounts(db, reports, ['node-01','node-02'])
        rows = db.query(UserHostAssociation).order_by(UserHostAssociation.host_id).all()
        assert rows[0].groups == 'users,docker' and rows[0].managed_sudo is True
        assert rows[1].groups == 'users,sudo' and rows[1].managed_sudo is False
        assert all(r.state == 'observed' and r.observed_at for r in rows)
        reconcile_accounts(db, [dict(report_type='accounts', hostname='node-01', accounts=[dict(username='operator',present=False)])], ['node-01'])
        assert rows[0].state == 'absent' and rows[1].state == 'observed'


def test_eligibility_checks_platform_freshness_and_recovery():
    host = device()
    op = OPERATION_BY_ID['system.update']
    assert operation_ineligibility(host, op) is None
    host.os_family = 'Alpine'
    assert 'Debian' in operation_ineligibility(host, op)
    host.os_family = 'Debian'
    host.maintenance_mode = 'unknown'
    assert 'maintenance mode' in operation_ineligibility(host, op)
    host.maintenance_mode = 'standalone'
    host.facts_stale = True
    assert 'fresh scan' in operation_ineligibility(host, op)
    host.facts_stale = False
    host.discovered_at = datetime.now(timezone.utc) - timedelta(hours=2)
    assert 'fresh scan' in operation_ineligibility(host, op)
    host.recovery_required = True
    assert 'recovery' in operation_ineligibility(host, op)
    assert operation_ineligibility(host, OPERATION_BY_ID['system.scan']) is None
    host.recovery_required = False
    host.facts = {'distribution':'Debian', 'service_manager':'openrc'}
    assert 'Ubuntu' in operation_ineligibility(host, OPERATION_BY_ID['system.bootstrap'])
    assert 'systemd' in operation_ineligibility(host, OPERATION_BY_ID['services.inspect'])


def test_incompatible_driver_installation_is_not_eligible():
    host = device()
    host.facts = {'nvidia_driver_package': 'nvidia-jetpack'}
    assert 'metapackage' in operation_ineligibility(host, OPERATION_BY_ID['nvidia.driver.manage'])


def test_package_approval_exact_scope_age_and_complete_results(database, tmp_path):
    with database() as db:
        one, two = device('node-01'), device('node-02')
        preview = job(status='success', finished_at=datetime.now(timezone.utc))
        preview.playbook = 'package_preview.yml'
        db.add_all([one,two,preview]); db.commit()
        directory = tmp_path/'job-results'/preview.job_id
        directory.mkdir(parents=True)
        report = {'schema_version':1,'report_type':'packages','hostname':'node-01','fingerprint':'a'*64,'changes':['Inst example [1] (2)']}
        (directory/'packages.json').write_text(json.dumps(report))
        assert _approved_package_plans(db, preview.job_id, [one]) == {'node-01':'a'*64}
        with pytest.raises(HTTPException, match='exact devices'):
            _approved_package_plans(db, preview.job_id, [one,two])
        preview.finished_at = datetime.now(timezone.utc)-timedelta(minutes=31)
        with pytest.raises(HTTPException, match='expired'):
            _approved_package_plans(db, preview.job_id, [one])
        preview.finished_at = datetime.now(timezone.utc)
        (directory/'packages.json').unlink()
        with pytest.raises(HTTPException, match='incomplete'):
            _approved_package_plans(db, preview.job_id, [one])


def test_missing_host_recap_is_not_success():
    assert parse_host_outcomes('PLAY RECAP\nnode-01 : ok=1 changed=0 unreachable=0 failed=0', ['node-01','node-02'])[-1]['status'] == 'not_checked'
    assert parse_host_outcomes('node-01 : ok=0 changed=0 unreachable=0 failed=0', ['node-01'])[0]['status'] == 'not_checked'


def test_partial_mutation_refreshes_only_success_and_requires_failed_host_recovery(database, tmp_path, monkeypatch):
    with database() as db:
        db.add_all([device('node-01'),device('node-02')]); db.commit()
    calls=[]
    def fake_execute(playbook, targets, values, credentials, job_id, timeout, append=False):
        calls.append((playbook,targets))
        log = runner.get_log_path(job_id)
        if playbook == 'host_facts.yml':
            scan = tmp_path/'scans'/job_id; scan.mkdir(parents=True)
            (scan/'node-01.json').write_text(json.dumps({'hostname':'node-01', 'os_family':'Debian','distribution':'Ubuntu','service_manager':'systemd'}))
            with log.open('a') as out: out.write('\n--- Post-operation facts ---\nnode-01 : ok=9 changed=0 unreachable=0 failed=0\n')
            return 0
        log.write_text('PLAY RECAP\nnode-01 : ok=5 changed=1 unreachable=0 failed=0\nnode-02 : ok=3 changed=1 unreachable=0 failed=1\n')
        return 2
    monkeypatch.setattr(runner,'_run_playbook_streaming',fake_execute)
    async def scenario():
        with database() as db:
            job_id=await runner.run_playbook(db,'manage_sudoers.yml',hosts=['node-01','node-02'],extra_vars={'root_users':['operator']})
        await asyncio.gather(*list(runner._BACKGROUND_TASKS))
        return job_id
    job_id=asyncio.run(scenario())
    with database() as db:
        completed=db.query(Job).filter_by(job_id=job_id).one()
        assert completed.status == 'recovery_required'
        assert [r['status'] for r in completed.device_results] == ['success','failed']
        one,two=db.query(Device).order_by(Device.hostname).all()
        assert not one.facts_stale and not one.recovery_required
        assert two.facts_stale and two.recovery_required
        assert db.query(DeviceReservation).count()==0
    assert calls == [('manage_sudoers.yml',['node-01','node-02']),('host_facts.yml',['node-01'])]


def test_idempotent_job_request_and_conflicting_reuse(database, monkeypatch):
    with database() as db:
        db.add(device());db.commit()
    async def scenario():
        with database() as db:
            with patch.object(runner, 'track_task', side_effect=lambda coroutine: coroutine.close()):
                key=str(uuid.uuid4())
                first=await runner.run_playbook(db,'host_facts.yml',hosts=['node-01'],request_key=key)
                second=await runner.run_playbook(db,'host_facts.yml',hosts=['node-01'],request_key=key)
                assert first == second and db.query(Job).count()==1
                with pytest.raises(runner.PlaybookRequestError,match='different operation'):
                    await runner.run_playbook(db,'reboot.yml',hosts=['node-01'],request_key=key)
    asyncio.run(scenario())


def test_cancel_running_change_is_rejected_but_pending_job_releases_reservation(database):
    with database() as db:
        host=device(); db.add(host);db.commit()
        running=job(status='running'); reserve_devices(db,running,[host])
        with pytest.raises(HTTPException,match='cannot be safely cancelled'):
            asyncio.run(cancel_job_output(running.job_id,db,'test'))
        running.status='pending';db.commit()
        asyncio.run(cancel_job_output(running.job_id,db,'test'))
        assert running.status=='cancelled' and db.query(DeviceReservation).count()==0
        runner._CANCELLED_JOBS.discard(running.job_id)


def test_operation_requires_target_confirmation_and_blocks_critical_service(database):
    with database() as db:
        host=device();db.add(host);db.commit()
        with pytest.raises(HTTPException,match='Confirm the exact'):
            asyncio.run(run_operation('system.reboot',OperationRunRequest(device_ids=[host.id]),db,'test'))
        with pytest.raises(HTTPException,match='non-critical'):
            asyncio.run(run_operation('services.manage',OperationRunRequest(device_ids=[host.id],confirmation=host.name,service_name='sshd.service'),db,'test'))


def test_migration_preserves_legacy_state_as_unverified(tmp_path, monkeypatch):
    from backend.config import settings
    url=f'sqlite:///{tmp_path}/migration.db'
    monkeypatch.setattr(settings,'database_url',url)
    config=Config('alembic.ini')
    command.upgrade(config,'0005_context_management')
    engine=create_engine(url)
    with engine.begin() as db:
        db.execute(text("INSERT INTO hosts (id, hostname) VALUES (1, 'old-node')"))
        db.execute(text("INSERT INTO managed_users (id, username, is_sudoer, groups) VALUES (1, 'operator', 1, 'sudo')"))
        db.execute(text('INSERT INTO user_host_assoc (user_id, host_id) VALUES (1, 1)'))
        db.execute(text("INSERT INTO jobs (job_id, playbook, status, target_hosts) VALUES ('old-job', 'reboot.yml', 'running', 'old-node')"))
    command.upgrade(config,'head')
    with sessionmaker(bind=engine)() as db:
        assert db.get(Device,1).facts_stale
        assert db.get(Device,1).maintenance_mode=='unknown'
        association=db.query(UserHostAssociation).one()
        assert association.managed_sudo is None and association.state=='unverified'
        reconcile_interrupted_jobs(db)
        assert db.get(Device,1).recovery_required
        assert db.query(Job).one().status=='recovery_required'
    engine.dispose()


def test_supervisor_terminates_child_on_executor_eof(tmp_path):
    supervisor=Path(runner.__file__).with_name('process_supervisor.py')
    read_fd,write_fd=os.pipe()
    child_pid_file=tmp_path/'pid'
    script="import os,time,pathlib; pathlib.Path(__import__('sys').argv[1]).write_text(str(os.getpid())); time.sleep(60)"
    proc=subprocess.Popen([sys.executable,str(supervisor),str(read_fd),sys.executable,'-c',script,str(child_pid_file)],pass_fds=(read_fd,))
    os.close(read_fd)
    try:
        deadline=time.monotonic()+5
        while not child_pid_file.exists() and time.monotonic()<deadline: time.sleep(.02)
        assert child_pid_file.exists()
        pid=int(child_pid_file.read_text())
        os.close(write_fd);write_fd=None
        proc.wait(timeout=10)
        with pytest.raises(ProcessLookupError): os.kill(pid,0)
    finally:
        if write_fd is not None: os.close(write_fd)
        if proc.poll() is None: proc.terminate();proc.wait(timeout=10)


def test_fifo_exit_before_reader_does_not_hang(tmp_path, monkeypatch):
    real_popen=subprocess.Popen
    def exit_before_fifo(command, **kwargs):
        return real_popen([sys.executable,'-c','raise SystemExit(17)'],**kwargs)
    monkeypatch.setattr(runner.settings,'ansible_dir',tmp_path)
    monkeypatch.setattr(runner.settings,'data_dir',tmp_path)
    monkeypatch.setattr(runner.subprocess,'Popen',exit_before_fifo)
    started=time.monotonic()
    assert runner._run_playbook_streaming('host_facts.yml',['node-01'],None,{},str(uuid.uuid4()),2)==17
    assert time.monotonic()-started<2


def test_reachy_interruption_preserves_remote_id_for_recovery(database, monkeypatch):
    from backend.routers import operations
    monkeypatch.setattr(operations, 'SessionLocal', database)
    monkeypatch.setattr(operations, 'reachy_request', lambda *a, **k: {'job_id':'remote-123'})
    monkeypatch.setattr(operations, '_poll_reachy_job', AsyncMock(side_effect=RuntimeError('connection interrupted')))
    with database() as db:
        host=device();host.transport='reachy_daemon';host.endpoint='127.0.0.1';db.add(host);db.commit()
    async def scenario():
        with database() as db:
            host=db.query(Device).one()
            result=operations._start_reachy_remote_jobs(db,[host],'test','reachy.software.update','Update software',str(uuid.uuid4()))
        await asyncio.gather(*list(runner._BACKGROUND_TASKS))
        return result['job_id']
    local_id=asyncio.run(scenario())
    with database() as db:
        completed=db.query(Job).filter_by(job_id=local_id).one()
        assert completed.status=='recovery_required'
        assert completed.device_results[0]['remote_job_id']=='remote-123'
        assert db.query(Device).one().recovery_required
        # Simulate abrupt exit instead of a normally recorded error.
        completed.status='running';db.commit()
        reconcile_interrupted_jobs(db)
        assert completed.device_results[0]['remote_job_id']=='remote-123'
        monkeypatch.setattr(operations,'reachy_request',lambda *a,**k:{'status':'done'})
        monkeypatch.setattr(operations,'probe_reachy',lambda *a:{'reachable':True,'detail':'Healthy','facts':{'version':'1.2'}})
        result=asyncio.run(operations._recover_reachy(db,[db.query(Device).one()],'test'))
        assert db.query(Job).filter_by(job_id=result['job_id']).one().status=='success'
        assert not db.query(Device).one().recovery_required
        assert not db.query(Device).one().facts_stale


def test_queued_jobs_are_counted_outside_recent_history(database):
    from backend.routers.jobs import job_summary
    with database() as db:
        db.add_all([job(status='pending') for _ in range(205)])
        db.add_all([job(status='success') for _ in range(300)])
        db.commit()
        assert job_summary(db,'test')['active_count']==205


def test_missing_post_operation_facts_requires_recovery(database, monkeypatch):
    with database() as db:
        db.add(device());db.commit()
    def fake_execute(playbook,targets,values,credentials,job_id,timeout,append=False):
        with runner.get_log_path(job_id).open('a' if append else 'w') as output:
            output.write('PLAY RECAP\nnode-01 : ok=2 changed=1 unreachable=0 failed=0\n')
        return 0
    monkeypatch.setattr(runner,'_run_playbook_streaming',fake_execute)
    async def scenario():
        with database() as db:
            job_id=await runner.run_playbook(db,'system_update.yml',hosts=['node-01'])
        await asyncio.gather(*list(runner._BACKGROUND_TASKS))
        return job_id
    job_id=asyncio.run(scenario())
    with database() as db:
        completed=db.query(Job).filter_by(job_id=job_id).one()
        assert completed.status=='recovery_required'
        assert completed.device_results[0]['status']=='verification_failed'
        assert db.query(Device).one().recovery_required


def test_failed_recovery_keeps_device_blocked(database, monkeypatch):
    with database() as db:
        host=device();host.recovery_required=True;db.add(host);db.commit()
    def fake_execute(playbook,targets,values,credentials,job_id,timeout,append=False):
        runner.get_log_path(job_id).write_text('PLAY RECAP\nnode-01 : ok=2 changed=0 unreachable=0 failed=1\n')
        return 2
    monkeypatch.setattr(runner,'_run_playbook_streaming',fake_execute)
    async def scenario():
        with database() as db:
            await runner.run_playbook(db,'recovery_check.yml',hosts=['node-01'])
        await asyncio.gather(*list(runner._BACKGROUND_TASKS))
    asyncio.run(scenario())
    with database() as db:
        assert db.query(Device).one().recovery_required
        assert db.query(Job).one().status=='failed'


@pytest.mark.parametrize('playbook', ['recovery_check.yml', 'system_update.yml'])
@pytest.mark.parametrize('scan_rc,second_recap,marker,expected_verified', [
    (0, 'ok=9 changed=0 unreachable=0 failed=0', True, ['node-01', 'node-02']),
    (2, 'ok=8 changed=0 unreachable=0 failed=1', True, ['node-01']),
    (0, '', True, ['node-01']),
    (1, 'ok=9 changed=0 unreachable=0 failed=0', True, []),
    (0, '', False, []),
])
def test_followup_scan_requires_report_and_successful_execution(
    database, tmp_path, monkeypatch, playbook, scan_rc, second_recap, marker, expected_verified,
):
    recovering = playbook == 'recovery_check.yml'
    with database() as db:
        db.add_all([device(name, recovery_required=recovering) for name in ('node-01', 'node-02')])
        db.commit()

    def fake_execute(name, targets, values, credentials, job_id, timeout, append=False):
        with runner.get_log_path(job_id).open('a' if append else 'w') as log:
            if name != 'host_facts.yml':
                log.write('PLAY RECAP\n')
                for target in targets:
                    log.write(f'{target} : ok=5 changed=0 unreachable=0 failed=0\n')
                return 0
            # A report can exist even when a later scan task or executor fails.
            scan = tmp_path / 'scans' / job_id
            scan.mkdir(parents=True)
            for target in targets:
                (scan / f'{target}.json').write_text(json.dumps({
                    'hostname': target, 'os_family': 'Debian', 'distribution': 'Ubuntu',
                    'service_manager': 'systemd',
                }))
            if marker:
                log.write('\n--- Post-operation facts ---\nPLAY RECAP\n')
                log.write('node-01 : ok=9 changed=0 unreachable=0 failed=0\n')
                if second_recap:
                    log.write(f'node-02 : {second_recap}\n')
            return scan_rc

    monkeypatch.setattr(runner, '_run_playbook_streaming', fake_execute)

    async def scenario():
        with database() as db:
            job_id = await runner.run_playbook(db, playbook, hosts=['node-01', 'node-02'])
        await asyncio.gather(*list(runner._BACKGROUND_TASKS))
        return job_id

    job_id = asyncio.run(scenario())
    with database() as db:
        completed = db.query(Job).filter_by(job_id=job_id).one()
        expected_status = 'success' if len(expected_verified) == 2 else 'failed' if recovering else 'recovery_required'
        assert completed.status == expected_status
        for host, outcome in zip(db.query(Device).order_by(Device.hostname), completed.device_results):
            verified = host.hostname in expected_verified
            assert outcome['status'] == ('success' if verified else 'verification_failed')
            assert host.facts_stale is not verified
            assert host.recovery_required is not verified
        assert db.query(DeviceReservation).count() == 0


def test_unknown_policy_allows_verification_but_still_blocks_disruptive_operations():
    from backend.capabilities import MAINTENANCE_OPERATIONS
    host = device()
    host.maintenance_mode = 'unknown'
    assert operation_ineligibility(host, OPERATION_BY_ID['system.recover']) is None
    for operation_id in MAINTENANCE_OPERATIONS:
        assert 'maintenance mode' in operation_ineligibility(host, OPERATION_BY_ID[operation_id])


@pytest.mark.parametrize('facts,expected', [
    ({}, False),
    ({'kubernetes_membership_detected': True}, True),
    ({'kubernetes_available': True}, True),
    ({'kubernetes_membership_detected': False, 'kubernetes_available': False}, False),
])
def test_inventory_retains_cluster_evidence_without_assigning_maintenance_policy(facts, expected):
    from backend.services.inventory_writer import _validated_device_vars
    host = device()
    host.maintenance_mode = 'unknown'
    host.facts = facts
    values = _validated_device_vars(host)
    assert values['fleet_maintenance_mode'] == 'unknown'
    assert values['fleet_kubernetes_membership_expected'] is expected


def test_reachy_poll_recovers_from_a_transient_restart_disconnect(database):
    from backend.routers import operations
    with patch.object(operations, 'reachy_request', side_effect=[RuntimeError('connection reset'), {'status':'done','logs':['ready']}]), patch.object(operations.asyncio,'sleep',new_callable=AsyncMock):
        asyncio.run(operations._poll_reachy_job(str(uuid.uuid4()),'robot','127.0.0.1',8000,'remote-123'))


def test_shutdown_cancels_queued_jobs_without_executing(database, monkeypatch):
    with database() as db:
        db.add(device());db.commit()
    executed=[]
    monkeypatch.setattr(runner,'_run_playbook_streaming',lambda *args: executed.append(args))
    async def scenario():
        monkeypatch.setattr(runner,'_JOB_SEMAPHORE',asyncio.Semaphore(0))
        with database() as db:
            await runner.run_playbook(db,'reboot.yml',hosts=['node-01'])
        await asyncio.sleep(0)
        await runner.shutdown_executor()
    asyncio.run(scenario())
    with database() as db:
        assert not executed
        assert db.query(Job).one().status=='cancelled'
        assert db.query(DeviceReservation).count()==0


def test_reachy_inspection_is_queued_reserved_and_refreshes_facts(database, monkeypatch):
    from backend.routers import operations
    monkeypatch.setattr(operations,'SessionLocal',database)
    probes=[]
    def probe(*args):
        probes.append(args)
        return {'reachable':True, 'detail':'Healthy', 'facts':{'daemon':{'state':'running'}}}
    monkeypatch.setattr(operations,'probe_reachy',probe)
    with database() as db:
        host=device();host.transport='reachy_daemon';db.add(host);db.commit()
    async def scenario():
        with database() as db:
            result=operations._start_reachy_inspection(db,[db.query(Device).one()],'test')
            assert db.query(DeviceReservation).count()==1
            assert probes==[]
        await asyncio.gather(*list(runner._BACKGROUND_TASKS))
        return result['job_id']
    job_id=asyncio.run(scenario())
    with database() as db:
        assert db.query(Job).filter_by(job_id=job_id).one().status=='success'
        assert db.query(DeviceReservation).count()==0
        assert not db.query(Device).one().facts_stale
        assert len(probes)==1
