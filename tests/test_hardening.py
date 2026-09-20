import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.config import Settings
from backend.capabilities import REACHY_APP_RESET
from backend.database import Base
from backend.schemas import (
    BulkPasswordResetRequest,
    BulkUserAdd,
    DeviceCreate,
    UserInfo,
)
from backend.services.ansible_runner import (
    FLEET_CREDENTIALS_VAR,
    FLEET_JOB_ID_VAR,
    FLEET_RESULTS_DIR_VAR,
    FLEET_SCAN_DIR_VAR,
    PlaybookRequestError,
    _run_playbook_streaming,
    _validate_extra_vars,
    redact_extra_vars,
)
from backend.services.inventory_writer import regenerate_inventory
from backend.services import login_throttle
from backend.services.secret_store import PREFIX, decrypt_secret, encrypt_secret
from backend.services.ssh_enrollment import (
    _fingerprint,
    get_agent_status,
    install_agent_key,
    trust_host_key,
)
from backend.services.tokens import TokenError, create_token, decode_token


class RequestValidationTests(unittest.TestCase):
    def test_user_info_rejects_unsafe_username_derived_from_email(self):
        with self.assertRaises(ValidationError):
            UserInfo(full_name="Bad User", email="bad;touch@corp.example")

    def test_bulk_user_add_requires_explicit_targeting(self):
        with self.assertRaises(ValidationError):
            BulkUserAdd(users=[UserInfo(full_name="Jane User", email="juser@example.com")])

    def test_bulk_user_add_accepts_all_devices_flag(self):
        payload = BulkUserAdd(
            users=[UserInfo(full_name="Jane User", email="juser@example.com")],
            all_devices=True,
        )
        self.assertTrue(payload.all_devices)
        self.assertIsNone(payload.device_ids)

    def test_password_auth_device_requires_password(self):
        with self.assertRaises(ValidationError):
            DeviceCreate(
                name="dgx-01",
                endpoint="192.0.2.10",
                ssh_user="fleetadmin",
                passwordless_ssh=False,
            )

    def test_key_auth_device_does_not_require_password(self):
        payload = DeviceCreate(
            name="dgx-01",
            endpoint="192.0.2.10",
            ssh_user="fleetadmin",
            passwordless_ssh=True,
        )
        self.assertIsNone(payload.ssh_password)

    def test_device_requires_explicit_remote_ssh_user(self):
        with self.assertRaises(ValidationError):
            DeviceCreate(
                name="dgx-01",
                endpoint="192.0.2.10",
                passwordless_ssh=True,
            )

    def test_full_name_rejects_template_expression(self):
        with self.assertRaises(ValidationError):
            UserInfo(full_name="{{ lookup('pipe', 'id') }}", email="safe@example.com")

    def test_full_name_rejects_shell_metacharacters(self):
        for full_name in ("Bad $(id)", "Bad `id`", "Bad | id", "Bad; id"):
            with self.subTest(full_name=full_name):
                with self.assertRaises(ValidationError):
                    UserInfo(full_name=full_name, email="safe@example.com")

    def test_password_rejects_template_expression(self):
        with self.assertRaises(ValidationError):
            BulkPasswordResetRequest(
                device_ids=[1],
                temp_password="SafePrefix{{ 7 * 7 }}",
            )


class RedactionTests(unittest.TestCase):
    def test_redacts_nested_secret_values(self):
        redacted = json.loads(
            redact_extra_vars(
                {
                    "default_password": "pw",
                    "nested": {"api_key": "token", "safe": "value"},
                    "items": [{"temp_password": "pw2"}],
                }
            )
        )
        self.assertEqual(redacted["default_password"], "***REDACTED***")
        self.assertEqual(redacted["nested"]["api_key"], "***REDACTED***")
        self.assertEqual(redacted["nested"]["safe"], "value")
        self.assertEqual(redacted["items"][0]["temp_password"], "***REDACTED***")

    def test_rejects_template_expressions_in_extra_vars(self):
        with self.assertRaises(PlaybookRequestError):
            _validate_extra_vars({"password": "{{ lookup('pipe', 'id') }}"})

    def test_rejects_reserved_connection_extra_vars(self):
        for key in (
            FLEET_CREDENTIALS_VAR,
            FLEET_JOB_ID_VAR,
            FLEET_RESULTS_DIR_VAR,
            FLEET_SCAN_DIR_VAR,
            "ansible_password",
            "ansible_become_password",
        ):
            with self.subTest(key=key):
                with self.assertRaises(PlaybookRequestError):
                    _validate_extra_vars({key: "not-allowed"})

class RuntimeConfigurationTests(unittest.TestCase):
    def test_defaults_are_rejected_in_development(self):
        config = Settings(
            _env_file=None,
            app_env="development",
            secret_key="changeme",
            admin_password="admin",
            host_secret_key="",
        )
        with self.assertRaises(RuntimeError):
            config.validate_runtime_settings()

    def test_cors_wildcard_is_rejected(self):
        config = Settings(_env_file=None, cors_origins="*")
        with self.assertRaises(RuntimeError):
            _ = config.cors_origin_list

    def test_ansible_forks_outside_safe_range_is_rejected(self):
        config = Settings(
            _env_file=None,
            secret_key="x" * 32,
            admin_password="a-secure-admin-password",
            host_secret_key="MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=",
            ansible_forks=101,
        )
        with self.assertRaisesRegex(RuntimeError, "ANSIBLE_FORKS"):
            config.validate_runtime_settings()


class HostCredentialTests(unittest.TestCase):
    def test_secret_store_fails_closed_without_key(self):
        with patch("backend.services.secret_store.settings.host_secret_key", ""):
            with self.assertRaises(RuntimeError):
                encrypt_secret("host-password")

    def test_secret_store_encrypts_credentials(self):
        key = "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA="
        with patch("backend.services.secret_store.settings.host_secret_key", key):
            encrypted = encrypt_secret("host-password")
            self.assertTrue(encrypted.startswith(PREFIX))
            self.assertEqual(decrypt_secret(encrypted), "host-password")

    def test_runtime_inventory_excludes_passwords_and_requires_known_hosts(self):
        host = SimpleNamespace(
            hostname="dgx-01",
            ip_address="10.2.3.4",
            machine_type="dgx_spark",
            ansible_user="fleet",
            encrypted_ansible_password="fernet:ciphertext",
            encrypted_ansible_become_password="fernet:other-ciphertext",
        )

        class Query:
            def all(self):
                return [host]

        class Database:
            def query(self, model):
                return Query()

        with tempfile.TemporaryDirectory() as directory:
            inventory = Path(directory) / "hosts.json"
            with patch("backend.services.inventory_writer.settings.inventory_file", inventory):
                regenerate_inventory(Database())
            content = inventory.read_text()
            validation = subprocess.run(
                [str(Path(sys.executable).with_name("ansible-inventory")), "-i", str(inventory), "--list"],
                capture_output=True,
                text=True,
            )

        parsed = json.loads(content)
        hostvars = parsed["all"]["children"]["dgx_spark"]["hosts"]["dgx-01"]
        self.assertEqual(hostvars["machine_type"], "dgx_spark")
        self.assertEqual(parsed["all"]["vars"]["ansible_python_interpreter"], "auto_silent")
        self.assertNotIn("ansible_password", content)
        self.assertNotIn("ansible_become_password", content)
        self.assertIn("StrictHostKeyChecking=yes", hostvars["ansible_ssh_common_args"])
        self.assertNotIn("accept-new", content)
        self.assertIn("unknown", parsed["all"]["children"])
        self.assertIn("managed_hosts", parsed["all"]["children"])
        self.assertIn("gpu", parsed["all"]["children"])
        self.assertIn("nvidia_gpu", parsed["all"]["children"])
        self.assertIn("dgx-01", parsed["all"]["children"]["gpu"]["hosts"])
        self.assertIn("dgx-01", parsed["all"]["children"]["managed_hosts"]["hosts"])
        self.assertEqual(validation.returncode, 0, validation.stderr)

    def test_unrecognized_legacy_machine_type_is_quarantined_as_unknown(self):
        host = SimpleNamespace(
            hostname="server-01",
            ip_address="192.0.2.20",
            machine_type="legacy-product",
            ansible_user="fleetadmin",
            encrypted_ansible_password=None,
            encrypted_ansible_become_password=None,
        )

        class Query:
            def all(self):
                return [host]

        class Database:
            def query(self, model):
                return Query()

        with tempfile.TemporaryDirectory() as directory:
            inventory = Path(directory) / "hosts.json"
            with patch("backend.services.inventory_writer.settings.inventory_file", inventory):
                regenerate_inventory(Database())
            parsed = json.loads(inventory.read_text())

        unknown_hostvars = parsed["all"]["children"]["unknown"]["hosts"]["server-01"]
        self.assertEqual(unknown_hostvars["machine_type"], "unknown")
        self.assertNotIn("server-01", parsed["all"]["children"]["gpu_node"]["hosts"])

    def test_dual_transport_reachy_only_enters_the_reset_inventory_group(self):
        host = SimpleNamespace(
            hostname="reachy-lab",
            endpoint="reachy-mini.local",
            ip_address="reachy-mini.local",
            transport="reachy_daemon",
            kind="robot",
            machine_type="unknown",
            ansible_user="pollen",
            encrypted_ansible_password=None,
            encrypted_ansible_become_password=None,
            capabilities_json=json.dumps([REACHY_APP_RESET]),
        )

        class Query:
            def all(self):
                return [host]

        class Database:
            def query(self, model):
                return Query()

        with tempfile.TemporaryDirectory() as directory:
            inventory = Path(directory) / "hosts.json"
            with patch("backend.services.inventory_writer.settings.inventory_file", inventory):
                regenerate_inventory(Database())
            parsed = json.loads(inventory.read_text())

        groups = parsed["all"]["children"]
        self.assertIn("reachy-lab", groups["reachy_ssh"]["hosts"])
        self.assertIn("reachy-lab", groups["robot"]["hosts"])
        self.assertNotIn("reachy-lab", groups["managed_hosts"]["hosts"])

    def test_fleet_ansible_secrets_use_named_pipe_not_process_arguments(self):
        captured = {"commands": []}

        class FakeProcess:
            returncode = 0
            stdout = []

            def __init__(self, command):
                captured["command"] = command
                extra_vars_arg = command[command.index("--extra-vars") + 1]
                extra_vars_path = Path(extra_vars_arg.removeprefix("@"))
                captured["extra_vars_path"] = extra_vars_path
                captured["extra_vars_is_fifo"] = extra_vars_path.is_fifo()

                def read_payload():
                    with extra_vars_path.open() as stream:
                        captured["payload"] = stream.read()

                self.reader = threading.Thread(target=read_payload)
                self.reader.start()

            def poll(self):
                return None if self.reader.is_alive() else 0

            def wait(self, timeout=None):
                self.reader.join(timeout=timeout)
                return 0

            def terminate(self):
                return None

            def kill(self):
                return None

        def fake_popen(command, **kwargs):
            captured["commands"].append(command)
            return FakeProcess(command)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "logs").mkdir()
            with (
                patch("backend.services.ansible_runner.settings.data_dir", root),
                patch("backend.services.ansible_runner.settings.ansible_dir", root),
                patch("backend.services.ansible_runner.settings.inventory_file", root / "hosts.json"),
                patch("backend.services.ansible_runner.subprocess.Popen", side_effect=fake_popen),
            ):
                result = _run_playbook_streaming(
                    "host_facts.yml",
                    ["dgx-01", "cpu-01"],
                    {"new_password": "account-password"},
                    {
                        "dgx-01": {"ansible_password": "host-password"},
                        "cpu-01": {"ansible_become_password": "sudo-password"},
                    },
                    "job-id",
                    30,
                )
            log_mode = (root / "logs" / "job-id.log").stat().st_mode & 0o777

        self.assertEqual(result, 0)
        self.assertEqual(log_mode, 0o600)
        self.assertEqual(len(captured["commands"]), 1)
        self.assertEqual(
            captured["command"][captured["command"].index("--limit") + 1],
            "dgx-01,cpu-01",
        )
        self.assertNotIn("account-password", " ".join(captured["command"]))
        self.assertNotIn("host-password", " ".join(captured["command"]))
        self.assertNotIn("sudo-password", " ".join(captured["command"]))
        self.assertTrue(captured["extra_vars_is_fifo"])
        self.assertFalse(captured["extra_vars_path"].exists())
        payload = json.loads(captured["payload"])
        self.assertEqual(payload["new_password"], "account-password")
        self.assertEqual(payload[FLEET_JOB_ID_VAR], "job-id")
        self.assertEqual(payload[FLEET_RESULTS_DIR_VAR], str(root / "job-results"))
        self.assertEqual(payload[FLEET_SCAN_DIR_VAR], str(root / "scans" / "job-id"))
        self.assertEqual(
            payload[FLEET_CREDENTIALS_VAR],
            {
                "dgx-01": {"ansible_password": "host-password"},
                "cpu-01": {"ansible_become_password": "sudo-password"},
            },
        )
        self.assertIn(FLEET_CREDENTIALS_VAR, payload["ansible_password"])
        self.assertIn(FLEET_CREDENTIALS_VAR, payload["ansible_become_password"])


class SshEnrollmentTests(unittest.TestCase):
    def test_sha256_fingerprint_uses_openssh_format(self):
        self.assertEqual(
            _fingerprint("ssh-ed25519", "dGVzdA=="),
            "SHA256:n4bQgYhMfWWaL+qgxVrQFaO/TxsrC4Is0V1sFbDwCgg",
        )

    def test_agent_status_requires_exactly_one_ed25519_identity(self):
        public_key = "ssh-ed25519 dGVzdA== fleet-management"
        completed = SimpleNamespace(returncode=0, stdout=public_key + "\n", stderr="")
        with (
            patch.dict(os.environ, {"SSH_AUTH_SOCK": "/run/fleet-agent/agent.sock"}, clear=False),
            patch.object(Path, "is_socket", return_value=True),
            patch("backend.services.ssh_enrollment.subprocess.run", return_value=completed),
        ):
            status = get_agent_status()
        self.assertTrue(status["ready"])
        self.assertEqual(
            status["fingerprints"],
            ["SHA256:n4bQgYhMfWWaL+qgxVrQFaO/TxsrC4Is0V1sFbDwCgg"],
        )

    def test_trust_host_key_rechecks_and_writes_managed_file(self):
        scanned = {
            "address": "192.0.2.10",
            "key_type": "ssh-ed25519",
            "public_key": "dGVzdA==",
            "fingerprint": "SHA256:n4bQgYhMfWWaL+qgxVrQFaO/TxsrC4Is0V1sFbDwCgg",
            "known_hosts_line": "192.0.2.10 ssh-ed25519 dGVzdA==",
        }
        with tempfile.TemporaryDirectory() as directory:
            known_hosts = Path(directory) / "ssh" / "known_hosts"
            with (
                patch("backend.services.ssh_enrollment.settings.ssh_known_hosts_file", known_hosts),
                patch("backend.services.ssh_enrollment.settings.ssh_known_hosts_seed_file", None),
                patch("backend.services.ssh_enrollment._scan_host_key", return_value=scanned),
            ):
                trust_host_key("192.0.2.10", scanned["fingerprint"])
            content = known_hosts.read_text()
            mode = known_hosts.stat().st_mode & 0o777
        self.assertEqual(content, scanned["known_hosts_line"] + "\n")
        self.assertEqual(mode, 0o600)

    def test_bootstrap_password_uses_environment_and_is_not_put_in_arguments(self):
        completed = SimpleNamespace(returncode=0, stdout="", stderr="")
        with patch(
            "backend.services.ssh_enrollment.subprocess.run",
            return_value=completed,
        ) as run:
            installed, _ = install_agent_key(
                "192.0.2.10",
                "fleetadmin",
                "one-time-password",
                "ssh-ed25519 dGVzdA== fleet-management",
            )
        command = run.call_args.args[0]
        self.assertTrue(installed)
        self.assertNotIn("one-time-password", " ".join(command))
        self.assertEqual(run.call_args.kwargs["env"]["SSHPASS"], "one-time-password")
        self.assertEqual(
            run.call_args.kwargs["input"],
            "ssh-ed25519 dGVzdA== fleet-management\n",
        )


class LoginThrottleTests(unittest.TestCase):
    def test_failures_persist_across_database_sessions(self):
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        local_session = sessionmaker(bind=engine)
        with (
            patch("backend.services.login_throttle.SessionLocal", local_session),
            patch("backend.services.login_throttle.settings.secret_key", "x" * 32),
        ):
            for _ in range(login_throttle.ACCOUNT_MAX_FAILURES):
                login_throttle.record_login_failure("192.0.2.10", "admin", now=1000)
            self.assertTrue(login_throttle.login_is_blocked("192.0.2.10", "admin", now=1001))
            login_throttle.clear_account_failures("admin")
            self.assertFalse(login_throttle.login_is_blocked("192.0.2.10", "admin", now=1001))


class TokenTests(unittest.TestCase):
    def test_token_round_trip_and_signature_check(self):
        token = create_token("admin", datetime.now(timezone.utc) + timedelta(minutes=5), "secret")
        self.assertEqual(decode_token(token, "secret")["sub"], "admin")
        with self.assertRaises(TokenError):
            decode_token(token, "wrong-secret")


if __name__ == "__main__":
    unittest.main()
