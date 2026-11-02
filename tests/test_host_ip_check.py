"""Verify discovery identity boundaries and the actual Ansible credential path."""

import asyncio
import base64
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import yaml

from backend.capabilities import OPERATION_BY_ID, operation_ineligibility
from backend.database import Base
from backend.models import Device, Job
from backend.routers import operations
from backend.schemas import OperationRunRequest
from backend.services import ansible_runner as runner
from backend.services.execution_state import is_read_only
from backend.services.inventory_writer import _validated_device_vars
from backend.services.job_results import get_job_results
from backend.services.secret_store import encrypt_secret


ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("host_ip_discovery", ROOT / "playbooks/files/host_ip_discovery.py")
discovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(discovery)
KEY = base64.b64encode(b"fixture host public key").decode()


def discovery_stubs(monkeypatch, resolved=(), scanned=(), matching=()):
    monkeypatch.setattr(discovery, "trusted_keys", lambda *args: {KEY})
    monkeypatch.setattr(discovery, "resolve", lambda *args: list(resolved))
    scans, probes = [], []
    def scan(*args):
        scans.append(args)
        return list(scanned)
    def match(ip, port, trusted):
        probes.append(ip)
        return {"ip": ip, "key": KEY} if ip in matching else None
    monkeypatch.setattr(discovery, "scan", scan)
    monkeypatch.setattr(discovery, "key_match", match)
    return scans, probes


def test_dns_key_match_avoids_subnet_scan(monkeypatch):
    scans, probes = discovery_stubs(monkeypatch, ["10.110.16.42"], matching=["10.110.16.42"])
    result = discovery.discover("node", "10.110.16.196", "known_hosts", "10.110.16.0/24")
    assert result["candidate_ip"] == "10.110.16.42"
    assert result["status"] == "candidate" and not scans
    assert probes == ["10.110.16.42"]
    assert "current_ip" not in result  # A key probe alone is not authentication.


def test_stale_dns_and_reassigned_old_ip_require_key_match(monkeypatch):
    scans, probes = discovery_stubs(monkeypatch, ["10.110.16.196"],
                                   ["10.110.16.196", "10.110.16.40", "10.110.16.42"], ["10.110.16.42"])
    result = discovery.discover("node", "10.110.16.196", "known_hosts", "10.110.16.0/24")
    assert result["candidate_ip"] == "10.110.16.42"
    assert len(scans) == 1 and probes.count("10.110.16.196") == 1


@pytest.mark.parametrize("matching,status", [([], "not_found"), (["10.110.16.40", "10.110.16.42"], "ambiguous")])
def test_absent_or_duplicate_keys_never_select_an_ip(monkeypatch, matching, status):
    discovery_stubs(monkeypatch, scanned=["10.110.16.40", "10.110.16.42"], matching=matching)
    result = discovery.discover("node", "10.110.16.196", "known_hosts", "10.110.16.0/24")
    assert result["status"] == status and result["candidate_ip"] is None
    assert "pinned_key" not in result


@pytest.mark.parametrize("subnet", ["10.110.0.0/16", "10.110.16.4/24", "::/64", "-iL /tmp/targets"])
def test_scan_scope_rejected_by_both_api_and_helper(subnet):
    with pytest.raises(ValueError):
        discovery.subnet_value(subnet)
    with pytest.raises(ValidationError):
        OperationRunRequest(device_ids=[1], discovery_subnet=subnet)


def test_missing_trust_stops_before_any_network_probe(tmp_path, monkeypatch):
    monkeypatch.setattr(discovery, "resolve", lambda *args: pytest.fail("Must not probe without trust"))
    with pytest.raises(ValueError, match="trust"):
        discovery.discover("node", "10.110.16.196", str(tmp_path / "missing"), "10.110.16.0/24")


def test_inventory_passes_the_configured_trust_path_to_discovery(tmp_path, monkeypatch):
    from backend.services import inventory_writer
    trust = tmp_path / "custom_known_hosts"
    monkeypatch.setattr(inventory_writer.settings, "ssh_known_hosts_file", trust)
    values = _validated_device_vars(Device(hostname="node", endpoint="192.0.2.10"))
    assert values["fleet_ssh_known_hosts_file"] == str(trust)
    assert str(trust) in values["ansible_ssh_common_args"]


def test_subnet_cannot_be_silently_ignored_by_another_operation():
    payload = OperationRunRequest(device_ids=[1], discovery_subnet="192.0.2.0/24")
    with pytest.raises(HTTPException, match="only supported by Find current IP"):
        asyncio.run(operations.run_operation("system.scan", payload, None, "tester"))


def test_revoked_key_is_not_reused(tmp_path, monkeypatch):
    trust = tmp_path / "known_hosts"
    trust.touch()
    monkeypatch.setattr(discovery, "run", lambda *args: SimpleNamespace(returncode=0, stdout=f"@revoked node ssh-ed25519 {KEY}\n"))
    with pytest.raises(ValueError, match="revoked"):
        discovery.trusted_keys(str(trust), ["node"], 22)


def test_revoked_hostname_alias_overrides_an_earlier_endpoint_match(tmp_path, monkeypatch):
    trust = tmp_path / "known_hosts"
    trust.touch()
    def lookup(argv):
        alias = argv[2]
        marker = "@revoked " if alias == "node" else ""
        return SimpleNamespace(returncode=0, stdout=f"{marker}{alias} ssh-ed25519 {KEY}\n")
    monkeypatch.setattr(discovery, "run", lookup)
    with pytest.raises(ValueError, match="revoked"):
        discovery.trusted_keys(str(trust), ["192.0.2.1", "node"], 22)


def test_nmap_scope_and_host_status_are_checked(monkeypatch):
    calls = []
    xml = '<nmaprun><host><status state="up"/><address addrtype="ipv4" addr="10.110.16.42"/></host><host><status state="down"/><address addrtype="ipv4" addr="10.110.16.43"/></host></nmaprun>'
    def run(argv, **kwargs):
        calls.append(argv)
        return SimpleNamespace(returncode=0, stdout=xml)
    monkeypatch.setattr(discovery, "run", run)
    assert discovery.scan(discovery.subnet_value("10.110.16.0/24"), 22) == ["10.110.16.42"]
    assert calls[0][:7] == ["nmap", "--unprivileged", "-sn", "-n", "-PS22", "--max-rate", "10"]
    xml = xml.replace("10.110.16.42", "10.110.17.42")
    with pytest.raises(ValueError, match="outside"):
        discovery.scan(discovery.subnet_value("10.110.16.0/24"), 22)


def test_operation_works_offline_with_stale_facts_and_reuses_request_scope(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        device = Device(hostname="lost-node", endpoint="10.110.16.196", transport="ssh", status="offline", facts_stale=True, recovery_required=True)
        db.add(device)
        db.commit()
        assert operation_ineligibility(device, OPERATION_BY_ID["system.ip.check"]) is None
        assert is_read_only("host_ip_check.yml")
        execute = AsyncMock(return_value="job-id")
        monkeypatch.setattr(operations, "run_playbook", execute)
        payload = OperationRunRequest(device_ids=[device.id], discovery_subnet="10.110.16.0/24", request_key="ip-check-request-1234")
        asyncio.run(operations.run_operation("system.ip.check", payload, db, "tester"))
        assert execute.call_args.kwargs["extra_vars"] == {"ip_discovery_subnet": "10.110.16.0/24"}
        assert execute.call_args.kwargs["hosts"] == ["lost-node"]
        db.add(Job(job_id="accepted", playbook="host_ip_check.yml", target_hosts="lost-node", triggered_by="tester",
                   request_key=payload.request_key, extra_vars=json.dumps({"ip_discovery_subnet":"10.110.16.0/24"})))
        db.commit()
        assert asyncio.run(operations.run_operation("system.ip.check", payload, db, "tester"))["job_id"] == "accepted"
        with pytest.raises(HTTPException, match="different operation"):
            asyncio.run(operations.run_operation("system.ip.check", payload.model_copy(update={"discovery_subnet":"10.110.17.0/24"}), db, "tester"))
        device.transport = "reachy_daemon"
        assert operation_ineligibility(device, OPERATION_BY_ID["system.ip.check"])
    engine.dispose()


@pytest.mark.parametrize("report_mode", ["verified", "unverified", "missing"])
def test_runner_reuses_stored_credentials_without_refreshing_stale_device(tmp_path, monkeypatch, report_mode):
    from cryptography.fernet import Fernet
    engine = create_engine(f"sqlite:///{tmp_path}/fleet.db")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    monkeypatch.setattr(runner, "SessionLocal", sessions)
    monkeypatch.setattr(runner.settings, "data_dir", tmp_path)
    monkeypatch.setattr(runner.settings, "host_secret_key", Fernet.generate_key().decode())
    monkeypatch.setattr(runner, "_JOB_SEMAPHORE", None)
    monkeypatch.setattr(runner.job_log_indexer, "ingest_completed_job", lambda *args: None)
    monkeypatch.setattr(runner, "regenerate_inventory", lambda *args: None)
    calls = []
    async def execute(playbook, targets, values, credentials, job_id, timeout):
        calls.append((playbook, targets, credentials))
        runner.get_log_path(job_id).write_text("PLAY RECAP\nlost-node : ok=8 changed=0 unreachable=0 failed=0\n")
        directory = tmp_path / "job-results" / job_id
        directory.mkdir(parents=True)
        if report_mode != "missing":
            (directory / "host_ip_lost-node.json").write_text(json.dumps({"schema_version":1,"report_type":"host_ip","hostname":"lost-node","status":"changed","verified":report_mode == "verified","current_ip":"10.110.16.42"}))
        return 0
    monkeypatch.setattr(runner, "_execute", execute)
    async def run():
        with sessions() as db:
            device = Device(hostname="lost-node", endpoint="10.110.16.196", ansible_user="existing-user", facts_stale=True,
                            recovery_required=True, encrypted_ansible_password=encrypt_secret("fixture-password"))
            db.add(device)
            db.commit()
            assert _validated_device_vars(device)["ansible_user"] == "existing-user"
            job_id = await runner.run_playbook(db, "host_ip_check.yml", hosts=["lost-node"])
        await asyncio.gather(*list(runner._BACKGROUND_TASKS))
        return job_id
    job_id = asyncio.run(run())
    assert calls == [("host_ip_check.yml", ["lost-node"], {"lost-node":{"ansible_password":"fixture-password"}})]
    with sessions() as db:
        device, job = db.query(Device).one(), db.query(Job).one()
        assert device.endpoint == "10.110.16.196" and device.facts_stale and device.recovery_required
        assert job.status == ("success" if report_mode == "verified" else "failed") and job.execution_kind == "read_only"
        assert "fixture-password" not in (job.extra_vars or "") + (job.output_log or "")
    if report_mode != "missing":
        assert get_job_results(job_id)[0]["current_ip"] == "10.110.16.42"
    engine.dispose()


@pytest.mark.parametrize("case,expected", [("changed", "changed"), ("unchanged", "unchanged"),
    ("mismatch", "not_found"), ("ambiguous", "ambiguous"), ("auth_failed", "verification_failed"), ("mixed", "changed")])
def test_real_playbook_with_mock_network_tools(tmp_path, monkeypatch, case, expected):
    ansible = shutil.which("ansible-playbook")
    assert ansible, "Use scripts/check-backend.sh so Ansible integration tests can run"
    private_key = tmp_path / "fixture-key"
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(private_key)], check=True)
    public_key = private_key.with_suffix(".pub").read_text().split()[1]
    trust = tmp_path / "known_hosts"
    trust.write_text(f"10.110.16.196 ssh-ed25519 {public_key}\n")
    # Hashed trust records must work as well as plain IP entries.
    subprocess.run(["ssh-keygen", "-H", "-f", str(trust)], check=True, capture_output=True)
    before_trust = trust.read_bytes()
    tools = tmp_path / "bin"
    tools.mkdir()
    log = tmp_path / "ssh-calls.jsonl"
    nmap = tools / "nmap"
    nmap.write_text('#!/usr/bin/env python3\nprint(\'<nmaprun><host><status state="up"/><address addrtype="ipv4" addr="10.110.16.42"/></host><host><status state="up"/><address addrtype="ipv4" addr="10.110.16.43"/></host></nmaprun>\')\n')
    keyscan = tools / "ssh-keyscan"
    keyscan.write_text('''#!/usr/bin/env python3
import os, sys
ip = sys.argv[-1]
case = os.environ['IP_TEST_CASE']
match = (case == 'unchanged' and ip == '10.110.16.196') or (case in ('changed', 'auth_failed', 'mixed') and ip == '10.110.16.42') or (case == 'ambiguous' and ip in ('10.110.16.42', '10.110.16.43'))
if match: print(ip + ' ssh-ed25519 ' + os.environ['IP_TEST_KEY'])
''')
    ssh = tools / "ssh"
    ssh.write_text('''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
args = sys.argv[1:]
assert 'StrictHostKeyChecking=yes' in args
assert 'HostKeyAlias=fleet-ip-discovery' in args
assert 'ForwardAgent=no' in args
pin = next(arg.split('=', 1)[1] for arg in args if arg.startswith('UserKnownHostsFile='))
assert Path(pin).read_text() == 'fleet-ip-discovery ssh-ed25519 ' + os.environ['IP_TEST_KEY'] + '\\n'
assert Path(pin).stat().st_mode & 0o777 == 0o600
with open(os.environ['IP_TEST_LOG'], 'a') as log: log.write(json.dumps(args) + '\\n')
if os.environ['IP_TEST_CASE'] == 'auth_failed': sys.exit(255)
print('actual-node-hostname')
''')
    for tool in (nmap, keyscan, ssh):
        tool.chmod(0o700)
    inventory = tmp_path / "inventory.yml"
    inventory.write_text(yaml.safe_dump({"all":{"children":{"managed_hosts":{"hosts":{"lost-node":{
        "ansible_host":"10.110.16.196", "ansible_user":"existing-user", "fleet_ssh_known_hosts_file":str(trust),
        "ansible_ssh_executable":str(ssh), "ansible_password":"", "ansible_become":True,
        "ansible_ssh_private_key_file":str(private_key),
        "ansible_ssh_common_args":f"-o StrictHostKeyChecking=yes -o UserKnownHostsFile={trust}",
    }}}}}}))
    if case == "mixed":
        content = yaml.safe_load(inventory.read_text())
        content["all"]["children"]["managed_hosts"]["hosts"]["untrusted-node"] = {
            "ansible_host":"10.110.16.197", "fleet_ssh_known_hosts_file":str(trust),
        }
        inventory.write_text(yaml.safe_dump(content))
    result = subprocess.run([ansible, "-i", str(inventory), str(ROOT / "playbooks/host_ip_check.yml"),
                             "-e", json.dumps({"ip_discovery_subnet":"10.110.16.0/24", "__fleet_results_dir":str(tmp_path / "results")})],
                            capture_output=True, text=True, timeout=40,
                            env={**os.environ, "PATH":str(tools) + os.pathsep + os.environ["PATH"], "ANSIBLE_NOCOLOR":"1",
                                 "IP_TEST_CASE":case, "IP_TEST_KEY":public_key, "IP_TEST_LOG":str(log)})
    report_path = tmp_path / "results/manual/host_ip_lost-node.json"
    assert report_path.exists(), result.stdout + result.stderr
    report = json.loads(report_path.read_text())
    assert report["status"] == expected, result.stdout + result.stderr
    assert report["verified"] is (case in {"changed", "unchanged", "mixed"})
    assert (result.returncode == 0) is (report["verified"] and case != "mixed")
    if case == "mixed":
        unresolved = json.loads((report_path.parent / "host_ip_untrusted-node.json").read_text())
        assert unresolved["status"] == "error" and not unresolved["verified"]
    assert trust.read_bytes() == before_trust
    if case in {"mismatch", "ambiguous"}:
        assert not log.exists(), "Credentials must never reach an unverified or ambiguous candidate"
    else:
        args = json.loads(log.read_text().splitlines()[0])
        assert 'User="existing-user"' in args
        assert f'IdentityFile="{private_key}"' in args
        assert "sudo" not in " ".join(args)
        pin = next(arg.split('=', 1)[1] for arg in args if arg.startswith('UserKnownHostsFile='))
        assert not Path(pin).exists()
    if not report["verified"]:
        assert report["current_ip"] is None
