#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
if [[ -x .venv/bin/python ]]; then
  export PATH="$PWD/.venv/bin:$PATH"
  python_bin="$PWD/.venv/bin/python"
else
  python_bin="$(command -v python3)"
fi
if ! command -v ansible-playbook >/dev/null; then
  echo "Install requirements-dev.txt and activate the environment; Ansible tests must not be skipped." >&2
  exit 1
fi
exec "$python_bin" -m pytest -q "$@"
