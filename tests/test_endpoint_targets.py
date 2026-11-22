"""Check both Make targets without restarting the stack or calling a provider."""

import os
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("target", ["start", "test"])
@pytest.mark.parametrize("failed_endpoint", ["", "embeddings"])
def test_endpoint_targets_run_every_check_and_propagate_failure(tmp_path, target, failed_endpoint):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "check_model_endpoint.py").symlink_to(ROOT / "scripts/check_model_endpoint.py")
    script = scripts / "start.sh"
    source = (ROOT / "scripts/start.sh").read_text()
    dispatch = '\ncase "$COMMAND" in\n'
    stubs = """
require_command() { :; }
require_env_file() { :; }
prepare_ssh() { :; }
sync_hosts() { :; }
compose() {
    if [[ "$1" != exec ]]; then echo "$*"; return 0; fi
    [[ "$2 $4 $5" == '-T python -' ]] || return 2
    echo "probe $3 $6"
    [[ "$6" != "$FAILED_ENDPOINT" ]]
}
"""
    script.write_text(source.replace(dispatch, stubs + dispatch))
    script.chmod(0o755)
    result = subprocess.run(
        ["make", "-f", str(ROOT / "Makefile"), target], cwd=tmp_path,
        env={**os.environ, "FAILED_ENDPOINT": failed_endpoint}, capture_output=True, text=True,
    )
    lines = result.stdout.splitlines()
    probes = [line for line in lines if line.startswith("probe ")]
    assert probes == ["probe web embeddings", "probe web parser", "probe nat reranker"]
    assert (result.returncode == 0) == (not failed_endpoint)
    ready = "[fleet] Fleet Manager is ready."
    assert (ready in lines) == (target == "start" and not failed_endpoint)
    if target == "start":
        wait = next(line for line in lines if line.startswith("up ") and "--wait " in line)
        assert lines.index(wait) < lines.index(probes[0])
        if not failed_endpoint:
            assert lines.index(probes[-1]) < lines.index(ready)
