"""Exercise agent readiness and targeted recovery without touching fleet access."""
import os
import subprocess
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(("identities", "status", "delay", "ready"), [
    ("ssh-ed25519 fixture-key fleet\n", 0, 0, True),
    ("", 1, 0, False),  # responsive but empty agent
    ("", 2, 0, False),  # lost agent connection
    ("", 0, 10, False),  # real timeout bounds an unresponsive agent
    ("ssh-ed25519 fixture-key fleet\nssh-ed25519 second-key other\n", 0, 0, False),
    ("ssh-rsa fixture-key fleet\n", 0, 0, False),
    ("", 0, 0, False),
])
def test_proxy_health_queries_identities_instead_of_socket_existence(tmp_path, identities, status, delay, ready):
    # Stub ssh-add, exercising the actual bounded query, installed script
    # and Compose command. Never load a real key or contact the host agent.
    command = tmp_path / "ssh-add"
    command.write_text(
        '#!/bin/sh\n'
        '[ "$*" = "-L" ] || exit 99\n'
        '[ "$SSH_AUTH_SOCK" = /run/fleet-agent/agent.sock ] || exit 99\n'
        'sleep "$TEST_DELAY"\nprintf "%s" "$TEST_IDENTITIES"\nexit "$TEST_STATUS"\n'
    )
    command.chmod(0o755)
    config = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
    check = config["services"]["ssh-agent-proxy"]["healthcheck"]
    assert check["test"] == ["CMD", "/usr/local/bin/check-ssh-agent"]
    result = subprocess.run(
        ["sh", str(ROOT / "ssh-agent-proxy/healthcheck.sh")],
        env={**os.environ, "PATH": f"{tmp_path}:{os.environ['PATH']}",
             "TEST_IDENTITIES": identities, "TEST_STATUS": str(status), "TEST_DELAY": str(delay)},
        capture_output=True, text=True, timeout=5,
    )
    assert (result.returncode == 0) == ready
    assert "fixture-key" not in result.stdout + result.stderr
    if status or delay:
        assert "make repair-ssh" in result.stderr


def test_repair_ssh_only_recreates_proxy_and_checks_running_web(tmp_path):
    # Execute the actual command dispatch with side effects replaced by a trace.
    source = (ROOT / "scripts/start.sh").read_text()
    dispatch = source.split('\ncase "$COMMAND" in\n', 1)[1]
    harness = tmp_path / "repair.sh"
    harness.write_text('''#!/bin/bash
set -eu
COMMAND=repair-ssh
require_command() { echo "require $*"; }
require_env_file() { echo env; }
prepare_ssh() { echo prepare; }
log() { :; }
compose() { echo "compose $*"; }
case "$COMMAND" in
''' + dispatch)
    result = subprocess.run(["bash", str(harness)], capture_output=True, text=True, check=True)
    lines = result.stdout.splitlines()
    assert lines[:4] == ["require docker", "env", "prepare", "compose config --quiet"]
    assert lines[4] == (
        "compose up -d --build --force-recreate --wait --wait-timeout 600 ssh-agent-proxy"
    )
    assert lines[5].startswith("compose exec -T web python -c ")
    assert "get_agent_status" in lines[5]
    assert len(lines) == 6
