"""Behavior checks using disposable Git checkouts and a fake Docker executable."""

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import collect_evidence as collector


class CollectorTests(unittest.TestCase):
    def test_redacts_credentials_preserving_diagnostic_text(self):
        private = "-" * 5 + " ".join(("BEGIN", "OPENSSH", "PRIVATE", "KEY")) + "-" * 5
        source = (
            'ERROR connection failed api_key="example alpha"\n'
            '{"admin_password": "example beta", "status": "failed"}\n'
            "Authorization: Bearer example-gamma\n"
            "authorization=Bearer example-delta\n"
            "Cookie: session=example-epsilon; other=value\n"
            "https://user:example-zeta@service.test/api?token=example-eta&ok=1\n"
            f"{private}\nexample-theta\n"
        )
        redacted = collector.redact(source)
        for suffix in ("alpha", "beta", "gamma", "delta", "epsilon", "zeta", "eta", "theta"):
            self.assertNotIn("example-" + suffix, redacted)
            self.assertNotIn("example " + suffix, redacted)
        self.assertIn("ERROR connection failed", redacted)
        self.assertIn('"status": "failed"', redacted)
        self.assertIn("&ok=1", redacted)

    def test_secret_keys_and_escaped_json_values_are_redacted(self):
        for key in ("SECRET_KEY", "HOST_SECRET_KEY", "ansible_ssh_pass", "ssh_passphrase", "EMBED_API_KEY"):
            value = 'sample escaped "credential" value'
            output = collector.redact(json.dumps({key: value, "status": "failed"}))
            self.assertNotIn("sample", output)
            self.assertNotIn("credential", output)
            self.assertIn('"status": "failed"', output)

    def test_process_timeout_and_output_limit_are_distinct_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            timeout = collector.run([sys.executable, "-c", "import time; time.sleep(5)"], directory, timeout=0.1)
            self.assertTrue(timeout["timed_out"])
            self.assertFalse(collector.succeeded(timeout))
            capped = collector.run(
                [sys.executable, "-c", "import sys; sys.stdout.write('x' * 1000000)"],
                directory, max_bytes=2048,
            )
            self.assertTrue(capped["byte_limit_reached"])
            self.assertLessEqual(len(capped["stdout"]) + len(capped["stderr"]), 2048)
            self.assertFalse(collector.succeeded(capped))

    def test_stderr_is_not_parsed_as_stdout_and_failures_stay_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            result = collector.run(
                [sys.executable, "-c", "import sys; print('web'); print('warning', file=sys.stderr); sys.exit(7)"],
                directory,
            )
            self.assertEqual(result["stdout"], "web\n")
            self.assertEqual(result["stderr"], "warning\n")
            self.assertEqual(result["returncode"], 7)
            self.assertFalse(collector.succeeded(result))
            missing = collector.run([str(Path(directory) / "missing-docker")], directory)
            self.assertTrue(missing["unavailable"])

    def test_windows_overlap_cap_and_reject_future_cursor(self):
        now = datetime(2026, 10, 20, 15, tzinfo=timezone.utc)
        previous = now - timedelta(hours=2)
        window = collector.log_window(now, collector.utc(previous))
        self.assertEqual(collector.timestamp(window["since"]), previous - timedelta(minutes=5))
        self.assertIsNone(window["gap"])
        old = collector.log_window(now, collector.utc(now - timedelta(days=4)))
        self.assertEqual(collector.timestamp(old["since"]), now - timedelta(days=1))
        self.assertIsNotNone(old["gap"])
        self.assertEqual(collector.timestamp(collector.log_window(now, override="4h")["since"]), now - timedelta(hours=4))
        with self.assertRaises(ValueError):
            collector.log_window(now, collector.utc(now + timedelta(minutes=1)))
        with self.assertRaises(ValueError):
            collector.timestamp("2026-10-20T12:00:00")

    def test_compose_json_supports_both_cli_shapes(self):
        rows = [{"Service": "web"}, {"Service": "nat"}]
        self.assertEqual(collector.json_rows(json.dumps(rows)), rows)
        self.assertEqual(collector.json_rows("\n".join(map(json.dumps, rows))), rows)
        self.assertEqual(collector.json_rows(""), [])

    def make_repo(self, directory):
        repo = Path(directory) / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        (repo / ".gitignore").write_text("data/\n")
        (repo / "docker-compose.yml").write_text("services: {}\n")
        marker = repo / "backend/services/ansible_runner.py"
        marker.parent.mkdir(parents=True)
        marker.write_text("# isolated fixture\n")
        subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
        subprocess.run(
            ["git", "-C", str(repo), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.test",
             "-c", "commit.gpgsign=false", "commit", "-qm", "fixture"],
            check=True,
        )
        return repo

    def fake_docker(self, directory):
        bindir = Path(directory) / "bin"
        bindir.mkdir()
        executable = bindir / "docker"
        executable.write_text(
            f"#!{sys.executable}\n"
            "import json, os, sys\n"
            "a = sys.argv[1:]\n"
            "if os.environ.get('FIXTURE_DOCKER_DOWN'):\n"
            "    print('daemon unavailable', file=sys.stderr); sys.exit(1)\n"
            "if a == ['context', 'show']: print('fixture')\n"
            "elif a == ['compose', 'config', '--services']:\n"
            "    print('web\\nnat'); print('interpolation warning', file=sys.stderr)\n"
            "elif a == ['compose', 'ps', '--all', '--format', 'json']:\n"
            "    print(json.dumps([{'ID': 'a'*12, 'Service': 'web', 'Project': 'fixture', 'State': 'running',\n"
            "                       'Command': 'PRIVATE_COMMAND', 'Labels': 'PRIVATE_LABEL'}]))\n"
            "elif a[:2] == ['inspect', '--format']:\n"
            "    assert '.Config.Env' not in a[2]\n"
            "    print(json.dumps({'status': 'running', 'image_id': 'fixture-image'}))\n"
            "elif a[:2] == ['compose', 'logs']:\n"
            "    assert '--until' in a and '--since' in a and '--tail' in a and '--follow' not in a\n"
            "    if a[-1] == 'web': print('ERROR fixture api_key=sample-credential')\n"
            "else:\n"
            "    print('FORBIDDEN COMMAND', file=sys.stderr); sys.exit(98)\n"
        )
        executable.chmod(0o700)
        return str(bindir) + os.pathsep + os.environ.get("PATH", "")

    def test_cli_collects_read_only_private_evidence_without_advancing_state(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = self.make_repo(directory)
            state_path = repo / ".agents/skills" / collector.SKILL / "references/review-state.json"
            state_path.parent.mkdir(parents=True)
            head = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
            state = {"schema_version": 1, "repository_reviewed_through": head, "docker_samples_reviewed_through": {}}
            state_path.write_text(json.dumps(state))
            before = state_path.read_bytes()
            env = {**os.environ, "PATH": self.fake_docker(directory)}
            result = subprocess.run(
                [sys.executable, collector.__file__, "--repo", str(repo)],
                capture_output=True, text=True, env=env, timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            evidence_path = Path(result.stdout.splitlines()[0])
            evidence = json.loads(evidence_path.read_text())
            self.assertEqual(state_path.read_bytes(), before)
            self.assertEqual(evidence_path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(evidence_path.parent.stat().st_mode & 0o777, 0o700)
            self.assertEqual(evidence["git"]["changes_since_review"]["stdout"], "")
            self.assertEqual(evidence["docker"]["selected_services"], ["web", "nat"])
            self.assertTrue(evidence["docker"]["logs"]["web"]["container_observed"])
            self.assertFalse(evidence["docker"]["logs"]["nat"]["container_observed"])
            for forbidden in ("PRIVATE_COMMAND", "PRIVATE_LABEL", "sample-credential", "FORBIDDEN COMMAND"):
                self.assertNotIn(forbidden, evidence_path.read_text())

    def test_docker_failure_keeps_git_evidence_and_records_gap(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = self.make_repo(directory)
            with patch.dict(os.environ, {"PATH": self.fake_docker(directory), "FIXTURE_DOCKER_DOWN": "1"}):
                evidence = collector.collect(repo, {}, datetime.now(timezone.utc))
            self.assertTrue(collector.succeeded(evidence["git"]["head"]))
            self.assertIn("gap", evidence["docker"])
            self.assertEqual(evidence["docker"]["logs"], {})

    def test_invalid_baseline_is_not_treated_as_empty_change_range(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = self.make_repo(directory)
            with patch.dict(os.environ, {"PATH": self.fake_docker(directory)}):
                evidence = collector.collect(
                    repo, {"repository_reviewed_through": "0" * 40}, datetime.now(timezone.utc),
                )
            self.assertIn("baseline_gap", evidence["git"])
            self.assertNotIn("changes_since_review", evidence["git"])

    def test_output_refuses_symlink_or_unignored_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = self.make_repo(directory)
            (repo / "data").symlink_to(directory)
            with self.assertRaises(ValueError):
                collector.private_output(repo)
            (repo / "data").unlink()
            (repo / ".gitignore").write_text("")
            with self.assertRaises(ValueError):
                collector.private_output(repo)

    def test_invalid_state_is_rejected_without_overwriting_it(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "state.json"
            for content in ('{"schema_version": 9}', '{"schema_version": 1, "repository_reviewed_through": "--all"}'):
                state.write_text(content)
                with self.assertRaises(ValueError):
                    collector.read_state(state)
                self.assertEqual(state.read_text(), content)


if __name__ == "__main__":
    unittest.main()
