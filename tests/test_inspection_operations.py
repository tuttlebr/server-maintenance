"""Exercise inspection boundaries: scope, missing mounts, and owner attribution."""
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

from backend.capabilities import OPERATION_BY_ID, operation_ineligibility
from backend.database import Base
from backend.models import Device
from backend.routers.operations import run_operation
from backend.schemas import OperationRunRequest
from backend.services.execution_state import is_read_only


def load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).parents[1] / 'playbooks/files' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


storage = load('storage_discovery')
gpu = load('gpu_usage')
USAGE = dict(total_mb=50, used_mb=25, avail_mb=25, use_pct=50)


def mount(target, source='/dev/sda1', fstype='ext4', options='rw'):
    return dict(target=target, source=source, fstype=fstype, options=options)


def test_storage_home_on_root_and_all_fstab_targets(tmp_path):
    fstab = tmp_path / 'fstab'
    fstab.write_text('# fixture\nUUID=root / ext4 defaults 0 1\n'
                     '/dev/sda2 /boot ext4 defaults 0 2\n'
                     'server:/share /data\\040pool nfs nofail,noauto 0 0\n'
                     '/home /alias none bind 0 0\n'
                     '/swapfile none swap sw 0 0\n')
    live = [mount('/'), mount('/boot', '/dev/sda2'), mount('/alias')]
    with patch.object(storage, 'filesystem_usage', return_value=USAGE) as usage, patch.object(storage, '_block_stack', return_value=[]):
        records = storage.build_home_fstab_inventory(live, storage.read_fstab(str(fstab)), '/home')
    assert [r['mountpoint'] for r in records] == ['/', '/boot', '/data pool', '/alias']
    assert records[0]['covers_home'] and records[0]['in_fstab']
    assert records[1]['total_mb'] == 50  # Small fstab mounts must not be filtered.
    assert records[2]['status'] == 'unmounted'
    assert records[2]['total_mb'] is None and records[2]['use_pct'] is None
    assert records[2]['optional'] and records[2]['noauto']
    assert [c.args[0] for c in usage.call_args_list] == ['/', '/boot', '/alias']


def test_separate_home_symlink_and_failed_network_usage():
    live = [mount('/'), mount('/srv'), mount('/srv/users'), mount('/network', 'nas:/share', 'nfs4')]
    with patch.object(storage, 'filesystem_usage', side_effect=[USAGE, None]), patch.object(storage, '_block_stack', return_value=[]):
        records = storage.build_home_fstab_inventory(live, [mount('/network')], '/srv/users/home')
    assert records[0]['mountpoint'] == '/srv/users' and records[0]['covers_home']
    assert records[1]['mounted'] and records[1]['status'] == 'unavailable'
    assert records[1]['avail_mb'] is None


def test_automount_is_observed_without_triggering_it():
    live = [mount('/'), mount('/home', 'systemd-1', 'autofs')]
    with patch.object(storage, 'filesystem_usage') as usage:
        records = storage.build_home_fstab_inventory(live, [mount('/home', 'nas:/home', 'nfs4', 'x-systemd.automount')], '/home')
    usage.assert_not_called()
    assert len(records) == 1
    assert records[0]['status'] == 'automount_pending' and records[0]['automount']


def test_fstab_read_failure_is_not_an_empty_success(tmp_path):
    with pytest.raises(OSError):
        storage.read_fstab(str(tmp_path / 'missing'))
    path = tmp_path / 'malformed'; path.write_text('UUID=bad /data\n')
    with pytest.raises(ValueError, match='line 1'):
        storage.read_fstab(str(path))
    with pytest.raises(ValueError, match='containing /home'):
        storage.build_home_fstab_inventory([], [], '/home')


def gpu_xml(util='65 %', memory='400 MiB', processes='', uuid='GPU-a'):
    return '<gpu><product_name>Test GPU</product_name><uuid>{}</uuid><utilization><gpu_util>{}</gpu_util></utilization><fb_memory_usage><total>1000 MiB</total><used>{}</used></fb_memory_usage>{}</gpu>'.format(uuid, util, memory, processes)


def process_xml(pid=42, kind='C', memory='300 MiB'):
    return '<process_info><pid>{}</pid><type>{}</type><process_name>/usr/bin/python</process_name><used_memory>{}</used_memory><gpu_instance_id>2</gpu_instance_id><compute_instance_id>1</compute_instance_id></process_info>'.format(pid, kind, memory)


def test_gpu_maps_compute_graphics_mig_and_same_pid_on_multiple_gpus():
    processes = '<processes>' + process_xml() + process_xml(43, 'G') + '</processes>'
    xml = '<nvidia_smi_log>' + gpu_xml(processes=processes) + gpu_xml(processes='<processes>'+process_xml()+'</processes>', uuid='GPU-b') + '</nvidia_smi_log>'
    resolver = lambda pid: dict(user='alice' if pid == 42 else 'root', uid=1001 if pid == 42 else 0)
    with patch.object(gpu, 'process_context', side_effect=lambda pid, cache: resolver(pid)) as resolve:
        report = gpu.build_report(xml, 'node-1')
    assert resolve.call_count == 2
    assert report['total_gpus'] == 2 and report['active_gpus'] == 2
    assert report['gpus'][0]['processes'][1]['process_type'] == 'G'
    assert report['gpus'][1]['processes'][0]['gpu_uuid'] == 'GPU-b'
    assert report['gpus'][0]['processes'][0]['gpu_instance_id'] == '2'
    assert report['user_summary'][0]['gpu_count'] == 2


@pytest.mark.parametrize('util,memory,processes,state', [
    ('0 %', '0 MiB', '<processes/>', 'free'),
    ('90 %', '0 MiB', '<processes/>', 'active'),
    ('0 %', '50 MiB', '<processes/>', 'allocated'),
    ('N/A', 'N/A', '<processes/>', 'unknown'),
    ('0 %', '0 MiB', '<processes>N/A</processes>', 'unknown'),
    ('0 %', '0 MiB', '', 'unknown'),
    ('0 %', 'N/A', '<processes>'+process_xml(memory='N/A')+'</processes>', 'idle_reserved'),
    ('N/A', 'N/A', '<processes>'+process_xml(memory='N/A')+'</processes>', 'in_use'),
])
def test_gpu_unknown_is_never_reported_as_zero_or_free(util, memory, processes, state):
    report = gpu.build_report('<nvidia_smi_log>'+gpu_xml(util, memory, processes)+'</nvidia_smi_log>', 'node', 'dgx_spark', lambda pid: {'user':'unknown'})
    result = report['gpus'][0]
    assert result['status'] == state
    if util == 'N/A': assert result['utilization_pct'] is None
    if memory == 'N/A': assert result['memory_used_mb'] is None and not result['memory_supported']
    assert report['free_gpus'] == (state == 'free')


def test_process_exited_and_numeric_uid_are_preserved(tmp_path):
    assert gpu.process_context(42, {}, str(tmp_path))['user'] == 'unknown'
    proc = tmp_path / '42'; proc.mkdir(); (proc / 'status').write_text('Uid:\t1000\t1001\t1001\t1001\n')
    with patch.object(gpu.pwd, 'getpwuid', side_effect=KeyError):
        result = gpu.process_context(42, {}, str(tmp_path))
    assert result['uid'] == 1001 and result['user'] == '1001'


def test_container_pod_namespace_and_label_do_not_replace_linux_owner(tmp_path):
    cid = 'a' * 64
    proc = tmp_path / '42'; proc.mkdir()
    (proc / 'status').write_text('Uid:\t0\t0\t0\t0\n')
    (proc / 'cgroup').write_text('0::/kubepods.slice/cri-containerd-{}.scope\n'.format(cid))
    payload = {'status': {'labels': {'io.kubernetes.pod.name': 'inference', 'io.kubernetes.pod.namespace': 'team', 'owner': 'alice'}}}
    with patch.object(gpu, 'run', side_effect=[RuntimeError('no Docker'), json.dumps(payload)]):
        result = gpu.process_context(42, {}, str(tmp_path))
    assert result['user'] == 'root' and result['namespace'] == 'team'
    assert result['workload_owner'] == 'alice' and result['source'] == 'kubernetes'


def test_gpu_empty_output_is_a_failure():
    with pytest.raises(ValueError, match='any GPU records'):
        gpu.build_report('<nvidia_smi_log/>', 'node')


@pytest.mark.parametrize('operation_id', ['storage.inspect', 'gpu.inspect'])
def test_inspection_launches_without_confirmation_or_recovery_prerequisites(operation_id):
    engine = create_engine('sqlite:///:memory:'); Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        host = Device(hostname='gpu-node', transport='ssh', facts_stale=False, discovered_at=datetime.now(timezone.utc), recovery_required=True)
        host.capabilities = ['gpu.inspect']; db.add(host); db.commit()
        operation = OPERATION_BY_ID[operation_id]
        assert operation_ineligibility(host, operation) is None
        assert is_read_only(operation.playbook)
        with patch('backend.routers.operations.run_playbook', AsyncMock(return_value='accepted')) as runner:
            result = asyncio.run(run_operation(operation_id, OperationRunRequest(device_ids=[host.id]), db, 'test'))
        assert result['job_id'] == 'accepted'
        assert runner.call_args.kwargs['playbook'] == operation.playbook
        assert runner.call_args.kwargs['hosts'] == ['gpu-node']
    engine.dispose()


def test_mixed_gpu_cpu_selection_is_rejected_as_a_whole():
    engine = create_engine('sqlite:///:memory:'); Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        cpu = Device(hostname='cpu-node', transport='ssh'); cpu.capabilities = []
        card = Device(hostname='gpu-node', transport='ssh'); card.capabilities = ['gpu.inspect']
        db.add_all([cpu, card]); db.commit()
        with patch('backend.routers.operations.run_playbook', AsyncMock()) as runner, pytest.raises(HTTPException, match='cpu-node'):
            asyncio.run(run_operation('gpu.inspect', OperationRunRequest(device_ids=[cpu.id, card.id]), db, 'test'))
        runner.assert_not_awaited()
    engine.dispose()
