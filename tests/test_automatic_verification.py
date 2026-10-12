"""Automatic health checks share the action's reservation and durable job."""
import asyncio
import json
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend.models import Device, DeviceReservation, Job
from backend.services import ansible_runner as runner
from backend.services.execution_state import reconcile_interrupted_jobs


@pytest.fixture
def workflow(tmp_path, monkeypatch):
    engine = create_engine(f'sqlite:///{tmp_path}/fleet.db')
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    monkeypatch.setattr(runner, 'SessionLocal', sessions)
    monkeypatch.setattr(runner.settings, 'data_dir', tmp_path)
    monkeypatch.setattr(runner, '_JOB_SEMAPHORE', None)
    monkeypatch.setattr(runner, 'regenerate_inventory', lambda db: None)
    monkeypatch.setattr(runner.job_log_indexer, 'ingest_completed_job', lambda job_id: None)
    with sessions() as db:
        for name, recovery in [('one', True), ('two', False), ('unselected', True)]:
            db.add(Device(hostname=name, transport='ssh', os_family='Debian', facts_stale=False, discovered_at=datetime.now(timezone.utc),
                          recovery_required=recovery, recovery_reason='Earlier incomplete job' if recovery else None))
        db.commit()
    behavior, calls = {}, []

    async def execute(playbook, targets, values, credentials, job_id, timeout, append=False):
        with sessions() as db:
            job = db.query(Job).filter_by(job_id=job_id).one()
            assert db.query(DeviceReservation).count() == 2
            calls.append((playbook, targets, job_id, job.phase))
            if playbook in {'system_update.yml', 'docker_cleanup.yml', 'user_management.yml'}:
                assert not any(host.recovery_required for host in db.query(Device).filter(Device.hostname.in_(targets)))
        if behavior.get('exception') and playbook == 'recovery_check.yml':
            raise RuntimeError('Injected health check interruption')
        before_change = not any(call[0] in {'system_update.yml', 'docker_cleanup.yml', 'reboot.yml', 'user_management.yml'} for call in calls)
        fail = (playbook == 'recovery_check.yml' and behavior.get('health_failure')) or (
            playbook == 'host_facts.yml' and behavior.get('scan_failure') and before_change)
        missing_scan = playbook == 'host_facts.yml' and behavior.get('missing_scan') and before_change
        silent_scan = playbook == 'host_facts.yml' and behavior.get('silent_post_scan') and not before_change
        no_action_recap = playbook in {'system_update.yml', 'docker_cleanup.yml', 'reboot.yml', 'user_management.yml'} and behavior.get('no_action_recap')
        if playbook == 'host_facts.yml' and not missing_scan:
            directory = tmp_path / 'scans' / job_id
            directory.mkdir(parents=True, exist_ok=True)
            for name in targets:
                (directory / f'{name}.json').write_text(json.dumps({
                    'hostname': name, 'os_family': 'Debian', 'distribution': 'Ubuntu',
                    'service_manager': 'systemd', 'docker_available': True,
                }))
        if playbook == 'reboot.yml':
            directory = tmp_path / 'job-results' / job_id
            directory.mkdir(parents=True)
            for name in targets:
                (directory / f'execution_{name}.json').write_text(json.dumps({'schema_version':1, 'report_type':'execution', 'hostname':name, 'mutation_started':True}))
        with runner.get_log_path(job_id).open('a' if append else 'w') as log:
            if silent_scan:
                return 0
            if append:
                log.write(f"\n{append if isinstance(append, str) else '--- Post-operation facts ---'}\n")
            if no_action_recap:
                log.write('ERROR: action did not complete\n')
                return behavior.get('reboot_rc', 2)
            if fail:
                log.write(f'fatal: [{targets[0]}]: FAILED! => {{"msg":"Required mounts are missing: /data"}}\n')
            log.write('PLAY RECAP\n')
            for name in targets:
                log.write(f'{name} : ok=3 changed=0 unreachable=0 failed={1 if fail else 0}\n')
        return behavior.get('health_rc', 2 if fail else 0) if playbook == 'recovery_check.yml' else (2 if fail else 0)

    monkeypatch.setattr(runner, '_execute', execute)

    async def run(playbook, retry=False):
        with sessions() as db:
            args = dict(playbook=playbook, hosts=['one', 'two'], request_key='same-request-key')
            job_id = await runner.run_playbook(db, **args)
            if retry:
                assert await runner.run_playbook(db, **args) == job_id
                with pytest.raises(runner.PlaybookRequestError, match='reserved'):
                    await runner.run_playbook(db, playbook='host_facts.yml', hosts=['one'])
        await asyncio.gather(*list(runner._BACKGROUND_TASKS))
        return job_id

    yield sessions, behavior, calls, run
    engine.dispose()


@pytest.mark.parametrize('playbook', ['system_update.yml', 'docker_cleanup.yml', 'user_management.yml'])
def test_automatic_check_continues_once_in_the_same_reserved_job(workflow, playbook):
    sessions, behavior, calls, run = workflow
    job_id = asyncio.run(run(playbook, retry=True))
    assert [call[0] for call in calls] == ['recovery_check.yml', 'host_facts.yml', playbook, 'host_facts.yml']
    assert [call[1] for call in calls] == [['one'], ['one'], ['one', 'two'], ['one', 'two']]
    assert [call[3] for call in calls] == ['checking_health', 'checking_facts', 'executing', 'refreshing_facts']
    assert {call[2] for call in calls} == {job_id}
    with sessions() as db:
        job = db.query(Job).one()
        assert job.status == 'success'
        assert all(item['status'] == 'success' for item in job.device_results)
        assert '--- Requested operation ---' in job.output_log
        assert not db.query(Device).filter_by(hostname='one').one().recovery_required
        assert db.query(Device).filter_by(hostname='unselected').one().recovery_required
        assert db.query(DeviceReservation).count() == 0


@pytest.mark.parametrize('failure', ['health_failure', 'scan_failure', 'missing_scan', 'timeout', 'process_failure', 'exception'])
def test_failed_automatic_check_never_starts_the_action_or_locks_other_devices(workflow, failure):
    sessions, behavior, calls, run = workflow
    behavior[failure] = True
    if failure in {'timeout', 'process_failure'}:
        behavior['health_rc'] = 124 if failure == 'timeout' else 1
    asyncio.run(run('system_update.yml'))
    assert all(call[0] in {'recovery_check.yml', 'host_facts.yml'} for call in calls)
    with sessions() as db:
        job = db.query(Job).one()
        assert job.status == 'failed'
        assert 'did not start' in job.error_summary
        if failure.endswith('failure') and failure != 'process_failure':
            assert '/data' in job.device_results[0]['detail']
        assert db.query(Device).filter_by(hostname='one').one().recovery_reason == 'Earlier incomplete job'
        assert not db.query(Device).filter_by(hostname='two').one().recovery_required
        assert db.query(DeviceReservation).count() == 0


@pytest.mark.parametrize('failure,expected_status', [('no_action_recap', 'failed'), ('silent_post_scan', 'recovery_required')])
def test_preflight_success_cannot_mask_a_later_failure(workflow, failure, expected_status):
    sessions, behavior, calls, run = workflow
    behavior[failure] = True
    asyncio.run(run('docker_cleanup.yml'))
    with sessions() as db:
        job = db.query(Job).one()
        assert job.status == expected_status
        assert all(item['status'] != 'success' for item in job.device_results)


def test_package_checks_do_not_need_recovery_verification(workflow):
    sessions, behavior, calls, run = workflow
    asyncio.run(run('package_preview.yml'))
    assert [call[0] for call in calls] == ['package_preview.yml']
    with sessions() as db:
        assert db.query(Job).one().status == 'success'
        assert db.query(Device).filter_by(hostname='one').one().recovery_required


@pytest.mark.parametrize('phase', ['checking_health', 'checking_facts'])
def test_restart_during_checks_does_not_imply_a_new_mutation(workflow, phase):
    sessions, *_ = workflow
    with sessions() as db:
        job = Job(job_id=str(uuid.uuid4()), playbook='system_update.yml', target_hosts='one,two',
                  status='running', phase=phase, execution_kind='mutation')
        db.add(job); db.commit()
        reconcile_interrupted_jobs(db)
        assert job.status == 'failed' and 'did not start' in job.error_summary
        assert db.query(Device).filter_by(hostname='one').one().recovery_reason == 'Earlier incomplete job'
        assert not db.query(Device).filter_by(hostname='two').one().recovery_required


def test_unconditional_reboot_bypasses_preflight_and_deduplicates_retries(workflow):
    sessions, behavior, calls, run = workflow
    behavior['health_failure'] = True
    asyncio.run(run('reboot.yml', retry=True))
    assert [call[0] for call in calls] == ['reboot.yml', 'host_facts.yml']
    assert all(call[1] == ['one', 'two'] for call in calls)
    with sessions() as db:
        assert db.query(Job).one().status == 'success'
        assert db.query(DeviceReservation).count() == 0
        # SSH returning is not proof that a prior host-health issue was repaired.
        assert db.query(Device).filter_by(hostname='one').one().recovery_reason == 'Earlier incomplete job'
        assert not db.query(Device).filter_by(hostname='two').one().recovery_required


@pytest.mark.parametrize('rc', [2, 124])
def test_failed_or_timed_out_reboot_never_claims_success(workflow, rc):
    sessions, behavior, calls, run = workflow
    behavior.update(no_action_recap=True, reboot_rc=rc)
    asyncio.run(run('reboot.yml'))
    assert [call[0] for call in calls] == ['reboot.yml']
    with sessions() as db:
        job = db.query(Job).one()
        assert job.status == 'recovery_required'
        assert all(item['status'] != 'success' for item in job.device_results)
        assert all(host.recovery_required for host in db.query(Device).filter(Device.hostname.in_(['one','two'])))
        assert db.query(DeviceReservation).count() == 0
