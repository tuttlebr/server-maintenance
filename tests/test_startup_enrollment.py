import io
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts import enroll_hosts

FINGERPRINT = "SHA256:n4bQgYhMfWWaL+qgxVrQFaO/TxsrC4Is0V1sFbDwCgg"
OTHER_FINGERPRINT = "SHA256:47DEQpj8HBSa+/TImW+5JCeuQeRkm5NMpJWZG3hSuFU"


class FakeClient:
    def __init__(self, *, existing=None, discovery=None):
        self.existing = existing or []
        self.discovery = discovery or {}
        self.discovered = []
        self.added = []

    def list_devices(self):
        return self.existing

    def discover(self, device):
        self.discovered.append(device)
        return self.discovery

    def add(self, device, fingerprint):
        self.added.append((device, fingerprint))
        return {"inventory_name": device["name"], **device}


def ssh_device(expected_fingerprint=None):
    suffix = f",{expected_fingerprint}" if expected_fingerprint else ","
    csv_text = (
        "name,endpoint,transport,ssh_user,passwordless_ssh,ssh_fingerprint\n"
        f"compute-01,192.0.2.10,ssh,fleet,true{suffix}\n"
    )
    return enroll_hosts.read_devices(io.StringIO(csv_text))[0]


def test_read_devices_uses_frontend_csv_contract():
    csv_text = (
        "name,endpoint,transport,ssh_user,ssh_password,become_password,"
        "passwordless_ssh,bootstrap_password,daemon_port\n"
        "compute-01,192.0.2.10,ssh,fleet,,,true,,\n"
        "reachy-lab,reachy.local,reachy_daemon,,,,true,,8000\n"
    )

    devices = enroll_hosts.read_devices(io.StringIO(csv_text))

    assert [device.name for device in devices] == ["compute-01", "reachy-lab"]
    assert devices[0].payload["daemon_port"] is None
    assert devices[1].payload["daemon_port"] == 8000


def test_matching_existing_device_is_skipped_without_discovery():
    device = ssh_device()
    client = FakeClient(
        existing=[
            {
                "inventory_name": "compute-01",
                "endpoint": "192.0.2.10",
                "transport": "ssh",
                "ssh_user": "fleet",
                "passwordless_ssh": True,
            }
        ]
    )

    assert enroll_hosts.enroll_devices([device], client, Path("unused"), io.StringIO())
    assert client.discovered == []
    assert client.added == []


def test_unverified_discovered_fingerprint_is_not_approved():
    device = ssh_device()
    client = FakeClient(
        discovery={
            "reachable": True,
            "trust_required": True,
            "fingerprint": FINGERPRINT,
        }
    )
    output = io.StringIO()

    with patch.object(enroll_hosts, "known_host_fingerprints", return_value=set()):
        success = enroll_hosts.enroll_devices([device], client, Path("unused"), output)

    assert not success
    assert client.added == []
    assert "needs independent verification" in output.getvalue()


def test_verified_seed_fingerprint_is_approved():
    device = ssh_device()
    client = FakeClient(
        discovery={
            "reachable": True,
            "trust_required": True,
            "fingerprint": FINGERPRINT,
        }
    )

    with patch.object(
        enroll_hosts, "known_host_fingerprints", return_value={FINGERPRINT}
    ):
        success = enroll_hosts.enroll_devices(
            [device], client, Path("unused"), io.StringIO()
        )

    assert success
    assert len(client.added) == 1
    assert client.added[0][1] == FINGERPRINT


def test_explicit_csv_fingerprint_is_approved_without_seed():
    device = ssh_device(FINGERPRINT)
    client = FakeClient(
        discovery={
            "reachable": True,
            "trust_required": True,
            "fingerprint": FINGERPRINT,
        }
    )

    with patch.object(enroll_hosts, "known_host_fingerprints", return_value=set()):
        success = enroll_hosts.enroll_devices(
            [device], client, Path("unused"), io.StringIO()
        )

    assert success
    assert client.added[0][1] == FINGERPRINT


def test_explicit_csv_fingerprint_mismatch_is_rejected():
    device = ssh_device(OTHER_FINGERPRINT)
    client = FakeClient(
        discovery={
            "reachable": True,
            "trust_required": True,
            "fingerprint": FINGERPRINT,
        }
    )

    with patch.object(enroll_hosts, "known_host_fingerprints", return_value=set()):
        success = enroll_hosts.enroll_devices(
            [device], client, Path("unused"), io.StringIO()
        )

    assert not success
    assert client.added == []


def test_changed_seed_fingerprint_is_rejected_even_if_persistently_trusted():
    device = ssh_device()
    client = FakeClient(
        discovery={
            "reachable": True,
            "trust_required": False,
            "fingerprint": FINGERPRINT,
        }
    )

    with patch.object(
        enroll_hosts, "known_host_fingerprints", return_value={OTHER_FINGERPRINT}
    ):
        success = enroll_hosts.enroll_devices(
            [device], client, Path("unused"), io.StringIO()
        )

    assert not success
    assert client.added == []


def test_revoked_known_host_key_cannot_be_used_as_a_pin():
    completed = SimpleNamespace(
        returncode=0,
        stdout="@revoked 192.0.2.10 ssh-ed25519 dGVzdA==\n",
        stderr="",
    )

    with (
        patch.object(Path, "is_file", return_value=True),
        patch.object(enroll_hosts.subprocess, "run", return_value=completed),
    ):
        try:
            enroll_hosts.known_host_fingerprints(Path("known_hosts"), "192.0.2.10")
        except enroll_hosts.EnrollmentError as exc:
            assert "marked revoked" in str(exc)
        else:
            raise AssertionError("revoked key was accepted")


def test_existing_endpoint_under_another_name_is_rejected():
    device = ssh_device()
    client = FakeClient(
        existing=[
            {
                "inventory_name": "other-name",
                "endpoint": "192.0.2.10",
                "transport": "ssh",
                "ssh_user": "fleet",
                "passwordless_ssh": True,
            }
        ]
    )

    success = enroll_hosts.enroll_devices(
        [device], client, Path("unused"), io.StringIO()
    )

    assert not success
    assert client.discovered == []
    assert client.added == []


def test_existing_password_device_does_not_require_plaintext_password_on_rerun():
    csv_text = (
        "name,endpoint,transport,ssh_user,ssh_password,passwordless_ssh\n"
        "compute-01,192.0.2.10,ssh,fleet,,false\n"
    )
    device = enroll_hosts.read_devices(io.StringIO(csv_text))[0]
    client = FakeClient(
        existing=[
            {
                "inventory_name": "compute-01",
                "endpoint": "192.0.2.10",
                "transport": "ssh",
                "ssh_user": "fleet",
                "passwordless_ssh": False,
            }
        ]
    )

    assert enroll_hosts.enroll_devices([device], client, Path("unused"), io.StringIO())
    assert client.discovered == []


def test_validation_error_drops_and_redacts_secret_input():
    secret = "sentinel-secret-value"
    content = json.dumps(
        {
            "detail": [
                {
                    "type": "value_error",
                    "loc": ["body", "device", "ssh_password"],
                    "msg": f"Invalid value {secret}",
                    "input": secret,
                }
            ]
        }
    ).encode()

    detail = enroll_hosts._validation_detail(422, content)
    redacted = enroll_hosts._redact_sensitive(
        detail, {"device": {"ssh_password": secret}}
    )

    assert secret not in redacted
    assert "input" not in redacted


def test_duplicate_headers_and_conflicting_fingerprint_aliases_are_rejected():
    duplicate = io.StringIO(
        "name,endpoint,transport,name\ncompute-01,192.0.2.10,ssh,duplicate\n"
    )
    conflicting = io.StringIO(
        "name,endpoint,transport,ssh_user,ssh_fingerprint,fingerprint\n"
        f"compute-01,192.0.2.10,ssh,fleet,{FINGERPRINT},{OTHER_FINGERPRINT}\n"
    )

    for stream in (duplicate, conflicting):
        try:
            enroll_hosts.read_devices(stream)
        except enroll_hosts.EnrollmentError:
            pass
        else:
            raise AssertionError("invalid CSV was accepted")
