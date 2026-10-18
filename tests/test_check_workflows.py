"""Exercise installed hook commands without executing a playbook or remote work."""
import shlex
import subprocess
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_shell_hook_checks_later_files_and_rejects_invalid_syntax(tmp_path):
    config = yaml.safe_load((ROOT / ".pre-commit-config.yaml").read_text())
    hook = next(h for repo in config["repos"] for h in repo["hooks"] if h["id"] == "shell-syntax")
    good, bad = tmp_path / "good.sh", tmp_path / "bad.sh"
    good.write_text("#!/usr/bin/env bash\nexit 0\n")
    bad.write_text("#!/usr/bin/env bash\nif true; then\n")
    command = shlex.split(hook["entry"])
    assert subprocess.run([*command, str(good)], capture_output=True).returncode == 0
    assert subprocess.run([*command, str(good), str(bad)], capture_output=True).returncode != 0


def test_pre_push_compiles_all_frontend_templates_in_addition_to_tests():
    config = yaml.safe_load((ROOT / ".pre-commit-config.yaml").read_text())
    hooks = {hook["id"]: hook for repo in config["repos"] for hook in repo["hooks"]}
    for hook_id in ("backend-tests", "frontend-tests", "frontend-build"):
        assert "pre-push" in hooks[hook_id]["stages"]
        assert hooks[hook_id]["always_run"] and not hooks[hook_id]["pass_filenames"]
