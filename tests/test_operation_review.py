import asyncio
import json
import tempfile
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.capabilities import OPERATIONS
from backend.database import Base
from backend.models import Device
from backend.routers.operations import run_operation
from backend.schemas import OperationRunRequest
from backend.services.ansible_runner import _process_scan_results


@pytest.fixture
def sessions():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    yield factory
    engine.dispose()


@pytest.mark.parametrize('operation', [op for op in OPERATIONS if op.playbook], ids=lambda op: op.id)
def test_every_ansible_operation_dispatches_only_selected_hosts(sessions, operation):
    with sessions() as db:
        for name in ('selected', 'unselected'):
            device = Device(hostname=name, transport='ssh', os_family='Debian', maintenance_mode='kubernetes', facts_stale=False, discovered_at=datetime.now(timezone.utc))
            device.facts = {'distribution':'Ubuntu','service_manager':'systemd','nvidia_driver_package':'nvidia-driver-580'}
            device.capabilities = [operation.required_capability]
            db.add(device)
        db.commit()
        selected = db.query(Device).filter_by(hostname='selected').one()
        run = AsyncMock(return_value='review-job')
        with patch('backend.routers.operations.run_playbook', run), patch('backend.routers.operations._approved_package_plans', return_value={'selected':'a'*64}):
            result = asyncio.run(run_operation(operation.id, OperationRunRequest(device_ids=[selected.id], confirmation='selected', service_name='nginx.service'), db, 'review'))
        assert result['job_id'] == 'review-job'
        assert run.await_args.kwargs['hosts'] == ['selected']
        assert run.await_args.kwargs['playbook'] == operation.playbook
        expected = {
            'system.update': {'fleet_approved_package_plans': {'selected':'a'*64}},
            'services.inspect': {'service_action':'status','service_name':'nginx.service'},
            'services.manage': {'service_action':'restarted','service_name':'nginx.service'},
            'kubernetes.drain.execute': {'drain_action':'drain'},
            'kubernetes.resume': {'drain_action':'resume'},
            'system.reboot': {'force_reboot': True},
            'nvidia.driver.manage': {'upgrade_mode': 'standard'},
            'nvidia.fabric_manager.manage': {'fabric_action': 'status'},
            'nvidia.mig.manage': {'mig_action': 'status'},
            'kubernetes.drain': {'drain_action': 'status'},
            'firmware.update': {'firmware_mode': 'update'},
        }
        assert run.await_args.kwargs['extra_vars'] == expected.get(operation.id)


def test_scan_cannot_consume_other_job_reports_or_restore_stale_online_state(sessions):
    with sessions() as db:
        db.add_all([Device(hostname='selected', status='online'), Device(hostname='other', status='offline')])
        db.commit()
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        old = root / 'scans' / 'previous-job'
        current = root / 'scans' / 'current-job'
        old.mkdir(parents=True)
        current.mkdir()
        stale_report = old / 'selected.json'
        stale_report.write_text(json.dumps({'hostname': 'selected', 'gpu_model': 'stale'}))
        foreign_report = current / 'other.json'
        foreign_report.write_text(json.dumps({'hostname': 'other', 'gpu_model': 'foreign'}))
        with patch('backend.services.ansible_runner.SessionLocal', sessions):
            _process_scan_results(['selected'], {'selected'}, scan_dir=current)
        with sessions() as db:
            assert db.query(Device).filter_by(hostname='selected').one().status == 'offline'
            assert db.query(Device).filter_by(hostname='other').one().status == 'offline'
        assert stale_report.exists()
        assert foreign_report.exists()


def test_failed_scan_without_report_directory_marks_target_offline(sessions):
    with sessions() as db:
        db.add(Device(hostname='selected', status='online'))
        db.commit()
    with tempfile.TemporaryDirectory() as directory:
        with patch('backend.services.ansible_runner.SessionLocal', sessions):
            _process_scan_results(['selected'], {'selected'}, scan_dir=Path(directory) / 'missing')
    with sessions() as db:
        assert db.query(Device).one().status == 'offline'


def test_current_job_scan_updates_facts_and_refreshes_inventory(sessions):
    with sessions() as db:
        db.add(Device(hostname='selected', status='offline'))
        db.commit()
    with tempfile.TemporaryDirectory() as directory:
        report_path = Path(directory) / 'selected.json'
        report_path.write_text(json.dumps({
            'hostname': 'selected', 'os_family': 'Debian',
            'os_version': 'Ubuntu 24.04', 'memory_mb': 65536,
            'reboot_required': True,
        }))
        with (
            patch('backend.services.ansible_runner.SessionLocal', sessions),
            patch('backend.services.ansible_runner.regenerate_inventory') as refresh,
        ):
            assert _process_scan_results(['selected'], scan_dir=Path(directory)) == []
            refresh.assert_called_once()
        assert not report_path.exists()
    with sessions() as db:
        device = db.query(Device).one()
        assert device.status == 'online'
        assert device.last_seen is not None
        assert device.os_version == 'Ubuntu 24.04'
        assert device.memory_gb == 64
        assert device.reboot_required
