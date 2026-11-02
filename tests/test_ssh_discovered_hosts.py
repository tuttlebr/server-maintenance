"""Exercise the interactive helper with a pseudo-terminal and fake network tools."""

import errno
import json
import os
from pathlib import Path
import pty
import select
import subprocess
import time

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/ssh-discovered-hosts.sh"


def run_interactive(tmp_path, subnet, answers, *, scan_fails=False):
    tools = tmp_path / "bin"
    tools.mkdir()
    log = tmp_path / "calls.jsonl"
    tool = '''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
name = Path(sys.argv[0]).name
with open(os.environ['FIXTURE_LOG'], 'a') as log:
    log.write(json.dumps([name, *sys.argv[1:]]) + '\\n')
if name == 'nmap':
    if os.environ['FIXTURE_SCAN_FAILS'] == '1': sys.exit(1)
    destination = sys.argv[sys.argv.index('-oG') + 1]
    Path(destination).write_text(''.join('Host: 192.0.2.' + str(n) + ' () Status: Up\\n' for n in [1, 2, 3]))
else:
    sys.exit(255)
'''
    for name in ("nmap", "ssh"):
        executable = tools / name
        executable.write_text(tool)
        executable.chmod(0o700)
    master, slave = pty.openpty()
    process = subprocess.Popen(
        ["bash", str(SCRIPT), "fixture-user", subnet], stdin=slave, stdout=slave, stderr=slave,
        env={**os.environ, "PATH": str(tools) + os.pathsep + os.environ["PATH"],
             "FIXTURE_LOG": str(log), "FIXTURE_SCAN_FAILS": "1" if scan_fails else "0"},
    )
    os.close(slave)
    output = bytearray()
    try:
        os.write(master, answers.encode())
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if select.select([master], [], [], 0.1)[0]:
                try:
                    block = os.read(master, 4096)
                except OSError as exc:
                    if exc.errno == errno.EIO:
                        break
                    raise
                if not block:
                    break
                output.extend(block)
            elif process.poll() is not None:
                break
        return_code = process.wait(timeout=1)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        os.close(master)
    return {"return_code": return_code, "output": output.decode(),
            "calls": [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []}


def test_interactive_discovery_connect_skip_quit_and_failed_ssh(tmp_path):
    result = run_interactive(tmp_path, "192.0.2.0/24", "\ns\nq\n")
    assert result["return_code"] == 0, result["output"]
    assert [call[0] for call in result["calls"]] == ["nmap", "ssh"]
    scan, ssh = result["calls"]
    assert scan[-1] == "192.0.2.0/24" and "--unprivileged" in scan
    assert ssh[-3:] == ["-l", "fixture-user", "192.0.2.1"]
    for option in ["StrictHostKeyChecking=ask", "ForwardAgent=no", "ForwardX11=no",
                   "ClearAllForwardings=yes", "PermitLocalCommand=no"]:
        assert option in ssh
    assert "SSH ended for 192.0.2.1 with status 255" in result["output"]
    assert not Path(scan[scan.index("-oG") + 1]).exists()


@pytest.mark.parametrize("subnet", ["192.0.0.0/16", "192.0.2.1/24", "::/64", "-iL /tmp/targets"])
def test_interactive_helper_rejects_invalid_scope_before_network_access(tmp_path, subnet):
    result = run_interactive(tmp_path, subnet, "q\n")
    assert result["return_code"] == 2
    assert result["calls"] == []


def test_interactive_helper_does_not_connect_after_scan_failure(tmp_path):
    result = run_interactive(tmp_path, "192.0.2.0/24", "\n", scan_fails=True)
    assert result["return_code"] == 1
    assert [call[0] for call in result["calls"]] == ["nmap"]
