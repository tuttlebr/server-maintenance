#!/usr/bin/env python3
"""Read-only, bounded Git/Compose evidence. Never updates review checkpoints."""

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import selectors
import signal
import subprocess
import tempfile
import time


SKILL = "server-maintenance-review-and-remediate"
SERVICE = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_.-]*\Z")
SHA = re.compile(r"(?:[a-f0-9]{40}|[a-f0-9]{64})\Z")
ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
PRIVATE_KEY = re.compile(
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?(?:-----END [A-Z0-9 ]*PRIVATE KEY-----|\Z)",
    re.DOTALL,
)
ASSIGNMENT = re.compile(
    r"""(?ix)(["']?\b(?:[a-z0-9_.-]*(?:password|passwd|passphrase|secret(?:[_-]?key)?|token|api[_-]?key|"""
    r"""private[_-]?key|(?:become|ssh|sudo)[_-]?pass)|authorization|cookie|set-cookie)["']?\s*[:=]\s*)"""
    r"""(?:"(?:\\.|[^"\\\n])*"|'(?:\\.|[^'\\\n])*'|[^\s,;&}\]]+)"""
)
AUTH_HEADER = re.compile(
    r"(?im)(\b(?:authorization|proxy-authorization|cookie|set-cookie)\s*:\s*)[^\r\n]+"
)
TOKEN = re.compile(r"\b(?:nvapi-|sk-)[A-Za-z0-9_-]{12,}|\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")
AUTH_VALUE = re.compile(r"\b(?:Bearer|Basic)\s+[A-Za-z0-9._~+/=-]+", re.I)
URL_AUTH = re.compile(r"([a-z][a-z0-9+.-]*://)[^/\s:@]+:[^/\s@]+@", re.I)
INSPECT_FORMAT = (
    '{"id":{{json .Id}},"image_id":{{json .Image}},'
    '"status":{{json .State.Status}},"started_at":{{json .State.StartedAt}},'
    '"finished_at":{{json .State.FinishedAt}},"exit_code":{{.State.ExitCode}},'
    '"oom_killed":{{.State.OOMKilled}},"restart_count":{{.RestartCount}},'
    '"health":{{with index .State "Health"}}{{json .Status}}{{else}}null{{end}}}'
)


def utc(value):
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def timestamp(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("timestamps must include a timezone")
    return result.astimezone(timezone.utc)


def redact(value):
    value = ANSI.sub("", value)
    value = PRIVATE_KEY.sub("[REDACTED PRIVATE KEY]", value)
    value = AUTH_HEADER.sub(r"\1[REDACTED]", value)
    value = AUTH_VALUE.sub("[REDACTED AUTH]", value)
    value = ASSIGNMENT.sub(r"\1[REDACTED]", value)
    value = URL_AUTH.sub(r"\1[REDACTED]@", value)
    return TOKEN.sub("[REDACTED TOKEN]", value)


def run(argv, cwd, timeout=20, max_bytes=1024 * 1024):
    """Bound both streams in memory; kill only our CLI process group on a limit."""
    result = {"argv": argv, "returncode": None, "timed_out": False, "byte_limit_reached": False}
    output = {"stdout": bytearray(), "stderr": bytearray()}
    started = time.monotonic()
    try:
        process = subprocess.Popen(
            argv, cwd=cwd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, start_new_session=True,
        )
    except OSError as error:
        return {**result, "stdout": "", "stderr": redact(str(error)), "unavailable": True}
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ, "stdout")
            selector.register(process.stderr, selectors.EVENT_READ, "stderr")
            remaining = max_bytes
            while selector.get_map():
                left = timeout - (time.monotonic() - started)
                if left <= 0:
                    result["timed_out"] = True
                    break
                for key, _ in selector.select(min(left, 0.2)):
                    chunk = os.read(key.fileobj.fileno(), min(65536, remaining + 1))
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    output[key.data].extend(chunk[:remaining])
                    remaining -= len(chunk)
                    if remaining < 0:
                        result["byte_limit_reached"] = True
                        break
                if result["byte_limit_reached"]:
                    break
            if not result["timed_out"] and not result["byte_limit_reached"]:
                try:
                    process.wait(timeout=max(0.001, timeout - (time.monotonic() - started)))
                except subprocess.TimeoutExpired:
                    result["timed_out"] = True
    finally:
        if result["timed_out"] or result["byte_limit_reached"] or process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        process.wait()
        process.stdout.close()
        process.stderr.close()
    result["returncode"] = process.returncode
    result.update({name: redact(value.decode("utf-8", errors="replace")) for name, value in output.items()})
    return result


def succeeded(result):
    return result["returncode"] == 0 and not result["timed_out"] and not result["byte_limit_reached"]


def read_state(path):
    if not path.exists():
        return {"schema_version": 1, "repository_reviewed_through": None, "docker_samples_reviewed_through": {}}
    state = json.loads(path.read_text())
    if not isinstance(state, dict) or state.get("schema_version") != 1:
        raise ValueError("unsupported review-state schema; preserve and migrate it before collecting")
    baseline = state.get("repository_reviewed_through")
    if baseline is not None and (not isinstance(baseline, str) or not SHA.fullmatch(baseline)):
        raise ValueError("repository_reviewed_through must be a full Git commit ID or null")
    cursors = state.get("docker_samples_reviewed_through", {})
    if not isinstance(cursors, dict):
        raise ValueError("docker_samples_reviewed_through must be a service-to-timestamp object")
    for service, value in cursors.items():
        if not SERVICE.fullmatch(service) or not isinstance(value, str):
            raise ValueError("invalid service cursor")
        timestamp(value)
    return state


def log_window(now, previous=None, override=None):
    if override:
        if re.fullmatch(r"\d+(?:\.\d+)?[smh]", override):
            delta = float(override[:-1]) * {"s": 1, "m": 60, "h": 3600}[override[-1]]
            start = now - timedelta(seconds=delta)
        else:
            start = timestamp(override)
        if start > now:
            raise ValueError("--since cannot be in the future")
        return {"since": utc(start), "until": utc(now), "source": "explicit", "gap": None}
    floor = now - timedelta(hours=24)
    if previous is None:
        return {"since": utc(floor), "until": utc(now), "source": "initial-24h", "gap": "older history not sampled"}
    last = timestamp(previous)
    if last > now:
        raise ValueError("saved Docker sample cursor is in the future")
    requested = last - timedelta(minutes=5)
    return {
        "since": utc(max(floor, requested)), "until": utc(now), "source": "saved-sample-with-5m-overlap",
        "gap": "prior interval exceeds 24h sampling cap" if requested < floor else None,
    }


def json_rows(text):
    stripped = text.strip()
    if not stripped:
        return []
    return json.loads(stripped) if stripped.startswith("[") else [json.loads(line) for line in stripped.splitlines()]


def collect(repo, state, now, services=None, since=None, tail=500, timeout=20, max_bytes=1024 * 1024):
    def command(*argv):
        return run(list(argv), repo, timeout, max_bytes)

    git = {
        "head": command("git", "rev-parse", "HEAD"),
        "branch": command("git", "branch", "--show-current"),
        "status": command("git", "status", "--short", "--untracked-files=normal"),
        "recent_history": command("git", "log", "-30", "--format=%H %cI %s"),
        "unstaged_paths": command("git", "diff", "--name-status"),
        "staged_paths": command("git", "diff", "--cached", "--name-status"),
        "baseline": state.get("repository_reviewed_through"),
    }
    if git["baseline"]:
        git["baseline_check"] = command("git", "merge-base", "--is-ancestor", git["baseline"], "HEAD")
        if succeeded(git["baseline_check"]):
            git["changes_since_review"] = command("git", "diff", "--name-status", git["baseline"], "HEAD", "--")
            git["commits_since_review"] = command(
                "git", "log", "-100", "--format=%H %cI %s", f'{git["baseline"]}..HEAD', "--",
            )
        else:
            git["baseline_gap"] = "Saved revision unavailable or not an ancestor; establish a new review baseline."
    else:
        git["baseline_gap"] = "No completed review baseline; recent history is only a starting sample."

    docker = {"context": command("docker", "context", "show")}
    discovery = command("docker", "compose", "config", "--services")
    docker["discovery"] = discovery
    docker["logs"] = {}
    if not succeeded(discovery):
        docker["gap"] = "Compose discovery failed; no runtime logs collected."
        return {"git": git, "docker": docker}
    discovered = discovery["stdout"].splitlines()
    if not discovered or any(not SERVICE.fullmatch(name) for name in discovered):
        docker["gap"] = "No valid Compose services discovered."
        return {"git": git, "docker": docker}
    selected = list(dict.fromkeys(services or discovered))
    unknown = set(selected) - set(discovered)
    if unknown:
        raise ValueError("service not present in current Compose configuration: " + ", ".join(sorted(unknown)))
    docker["selected_services"] = selected
    ps = command("docker", "compose", "ps", "--all", "--format", "json")
    docker["ps"] = {key: value for key, value in ps.items() if key != "stdout"}
    containers = []
    if succeeded(ps):
        try:
            fields = ("ID", "Service", "Project", "Name", "Image", "State", "Health", "ExitCode")
            containers = [{key: row.get(key) for key in fields} for row in json_rows(ps["stdout"])]
        except (ValueError, AttributeError, TypeError):
            docker["ps"]["parse_error"] = "Unable to parse Compose container rows."
    docker["containers"] = containers
    docker["inspection"] = {}
    for container in containers:
        identifier = container.get("ID") or ""
        if container["Service"] in selected and re.fullmatch(r"[a-f0-9]{12,64}", identifier):
            docker["inspection"][identifier] = command("docker", "inspect", "--format", INSPECT_FORMAT, identifier)
    cursors = state.get("docker_samples_reviewed_through", {})
    for service in selected:
        window = log_window(now, cursors.get(service), since)
        result = command(
            "docker", "compose", "logs", "--no-color", "--timestamps", "--since", window["since"],
            "--until", window["until"], "--tail", str(tail), service,
        )
        count = len(result["stdout"].splitlines())
        docker["logs"][service] = {
            **result, "window": window, "line_count": count,
            "tail_limit_per_container": tail, "possibly_tail_limited": count >= tail,
            "container_observed": any(row["Service"] == service for row in containers),
        }
    return {"git": git, "docker": docker}


def private_output(repo):
    """Refuse symlinked output parents and tracked/nonignored destinations."""
    base = repo
    for part in ("data", "skill-reviews"):
        base = base / part
        if base.is_symlink():
            raise ValueError("evidence output parent must not be a symlink")
        base.mkdir(mode=0o700, exist_ok=True)
    ignored = run(["git", "check-ignore", "-q", "--", "data/skill-reviews/evidence.json"], repo)
    tracked = run(["git", "ls-files", "--", "data/skill-reviews"], repo)
    if not succeeded(ignored) or not succeeded(tracked) or tracked["stdout"].strip():
        raise ValueError("evidence destination must be Git-ignored and untracked")
    return Path(tempfile.mkdtemp(prefix=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-"), dir=base))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--service", action="append", help="select a discovered Compose service; repeatable")
    parser.add_argument("--since", help="UTC/offset timestamp or duration such as 30m or 24h")
    parser.add_argument("--tail", type=int, default=500)
    parser.add_argument("--timeout", type=float, default=20, help="seconds per CLI call")
    parser.add_argument("--max-bytes", type=int, default=1024 * 1024, help="combined output cap per CLI call")
    args = parser.parse_args()
    if not 1 <= args.tail <= 10000 or not 0 < args.timeout <= 60 or not 1024 <= args.max_bytes <= 16 * 1024 * 1024:
        parser.error("use tail 1..10000, timeout (0,60], and max-bytes 1024..16777216")
    repo = args.repo.resolve()
    now = datetime.now(timezone.utc)
    try:
        root = run(["git", "rev-parse", "--show-toplevel"], repo)
        if not succeeded(root):
            raise ValueError("--repo must identify a Git checkout")
        repo = Path(root["stdout"].strip()).resolve()
        for marker in ("docker-compose.yml", "backend/services/ansible_runner.py"):
            if not (repo / marker).is_file():
                raise ValueError("--repo must identify the Fleet Manager server-maintenance checkout")
        state = read_state(repo / ".agents" / "skills" / SKILL / "references" / "review-state.json")
        if args.since:
            log_window(now, override=args.since)
        output = private_output(repo)
        evidence = {
            "schema_version": 1, "collected_at": utc(now),
            "redaction": "best effort; keep local and inspect before sharing",
            "coverage": "bounded samples; review cursors unchanged",
            **collect(repo, state, now, args.service, args.since, args.tail, args.timeout, args.max_bytes),
        }
        path = output / "evidence.json"
        with open(path, "x", encoding="utf-8", opener=lambda name, flags: os.open(name, flags, 0o600)) as stream:
            json.dump(evidence, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
        print(path)
        failed = [
            name for name, result in evidence["docker"]["logs"].items()
            if not succeeded(result) or not result["container_observed"]
        ]
        if evidence["docker"].get("gap") or failed:
            print("Partial runtime evidence; inspect command outcomes and preserve unavailable-service cursors.")
        return 0
    except (ValueError, OSError) as error:
        parser.exit(2, f"Collection failed: {redact(str(error))}\n")


if __name__ == "__main__":
    raise SystemExit(main())
