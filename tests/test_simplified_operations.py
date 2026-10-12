import asyncio
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.capabilities import OPERATIONS, OPERATION_BY_ID, operation_ineligibility
from backend.database import Base
from backend.models import Device, Job
from backend.routers.operations import list_operations, run_operation
from backend.schemas import OperationRunRequest
from backend.services.execution_state import parse_host_outcomes

spec = importlib.util.spec_from_file_location('container_cleanup', Path(__file__).parents[1] / 'playbooks/files/container_cleanup.py')
cleanup_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cleanup_module)


@pytest.fixture
def db():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as session:
        device = Device(hostname='node-01', transport='ssh', os_family='Debian', maintenance_mode='standalone', facts_stale=False, discovered_at=datetime.now(timezone.utc))
        device.capabilities = ['system.update', 'containers.cleanup']
        session.add(device)
        session.commit()
        yield session
    engine.dispose()


def test_empty_fleet_still_explains_the_eight_actions(db):
    db.query(Device).delete(); db.commit()
    catalog = list_operations(db, 'test')
    assert [op.id for op in catalog] == ['system.scan', 'system.packages.preview', 'system.update', 'containers.cleanup', 'system.reboot', 'storage.inspect', 'gpu.inspect', 'reachy.daemon.restart']
    assert all(op.eligible_count == 0 for op in catalog)


@pytest.mark.parametrize('family', ['RedHat', 'Alpine', None])
def test_package_actions_only_support_apt(db, family):
    host = db.query(Device).one(); host.os_family = family
    for operation in [OPERATION_BY_ID[key] for key in ('system.packages.preview', 'system.update')]:
        assert 'apt' in operation_ineligibility(host, operation)


def test_stale_inventory_requires_discovery_even_during_recovery(db):
    host = db.query(Device).one(); host.facts_stale = True; host.discovered_at = None
    assert 'Scan devices first' in operation_ineligibility(host, OPERATION_BY_ID['system.update'])
    host.recovery_required = True
    assert 'Scan devices first' in operation_ineligibility(host, OPERATION_BY_ID['system.update'])


def test_accepted_retry_survives_device_recovery_and_does_not_relaunch(db):
    host = db.query(Device).one(); host.recovery_required = True
    job = Job(job_id='a'*36, playbook='docker_cleanup.yml', target_hosts=host.hostname, status='running', triggered_by='test', request_key='retry-key-1234567')
    db.add(job); db.commit()
    with patch('backend.routers.operations.run_playbook', AsyncMock()) as runner:
        response = asyncio.run(run_operation('containers.cleanup', OperationRunRequest(device_ids=[host.id], request_key=job.request_key), db, 'test'))
    assert response['job_id'] == job.job_id
    runner.assert_not_awaited()
    with pytest.raises(HTTPException, match='different operation'):
        asyncio.run(run_operation('system.packages.preview', OperationRunRequest(device_ids=[host.id], request_key=job.request_key), db, 'test'))


def test_account_panel_has_explicit_bulk_endpoints():
    from backend.main import app
    assert '/api/v2/users/bulk-add' in app.openapi()['paths']
    assert '/api/v2/users/bulk-update' in app.openapi()['paths']
    assert '/api/v2/users/csv-preview' in app.openapi()['paths']


def test_errors_are_attached_to_the_failed_device():
    log = 'fatal: [node-01]: FAILED! => {\n"changed": false, "msg": "Package lists changed. Check again."\n}\nPLAY RECAP\nnode-01 : ok=2 changed=0 unreachable=0 failed=1\nnode-02 : ok=5 changed=0 unreachable=0 failed=0'
    outcomes = parse_host_outcomes(log, ['node-01','node-02'])
    assert outcomes[0]['detail'] == 'Package lists changed. Check again.'
    assert 'detail' not in outcomes[1]


def test_cleanup_covers_all_namespaces_without_deleting_containers_volumes_or_networks():
    calls = []
    def run(argv, **kwargs):
        calls.append(argv)
        if argv == ['nerdctl','namespace','ls','--quiet']:
            return 0, 'default\nk8s.io\nmoby\ncustom\n'
        return 0, 'Total reclaimed space: 0B'
    result = cleanup_module.cleanup(run=run, which=lambda cmd: '/usr/bin/'+cmd)
    assert result['success']
    for namespace in ['default','k8s.io','custom']:
        assert ['nerdctl','--namespace',namespace,'image','prune','--all','--force'] in calls
    assert not any('moby' in call for call in calls)
    assert ['docker','builder','prune','--all','--force'] in calls
    assert ['nerdctl','builder','prune','--all','--force'] in calls
    assert not any(word in call for call in calls for word in ['container','volume','network','system','rm'])


def test_missing_buildkit_is_reported_as_skipped():
    def run(argv, **kwargs):
        return (0, 'default') if argv == ['nerdctl','namespace','ls','--quiet'] else (0, '')
    result = cleanup_module.cleanup(run=run, which=lambda cmd: '/usr/bin/nerdctl' if cmd == 'nerdctl' else None)
    assert result['success']
    assert any(step['status'] == 'skipped' and 'buildctl' in step['output'] for step in result['steps'])


def test_runtime_failure_does_not_mask_other_runtime_results():
    def run(argv, **kwargs):
        if argv == ['docker','info']: return 1, 'Cannot connect'
        if argv == ['nerdctl','namespace','ls','--quiet']: return 0, 'k8s.io'
        return 0, 'Done'
    result = cleanup_module.cleanup(run=run, which=lambda cmd: '/usr/bin/'+cmd)
    assert not result['success']
    assert any(step['label'] == 'containerd / k8s.io' and step['status'] == 'success' for step in result['steps'])


def test_no_runtime_is_not_a_success():
    result = cleanup_module.cleanup(which=lambda cmd: None)
    assert not result['success']
    assert result['mutation_started'] is False
