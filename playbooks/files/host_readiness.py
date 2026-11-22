"""Collect read-only host observations before maintenance."""

import json
import os
import re
import subprocess
from pathlib import Path


def finding(status, detail, advice=""):
    return {"status": status, "detail": detail, "advice": advice}


def root_capacity():
    try:
        fs = os.statvfs("/")
    except OSError:
        return finding("unavailable", "Could not read root filesystem capacity.")
    if fs.f_flag & os.ST_RDONLY:
        return finding("attention", "The root filesystem is read-only.", "Review the mount state before installing updates.")
    # Match df's block accounting: reserved blocks are not available to general workloads.
    available = max(0, fs.f_bavail)
    used = fs.f_blocks - fs.f_bfree
    if used + available <= 0:
        return finding("unavailable", "Root filesystem capacity was unavailable.")
    pct = 100 * used / (used + available)
    detail = f"{pct:.1f}% used on / ({available * fs.f_frsize / 1024**3:.1f} GiB available)."
    if pct >= 85:
        return finding("attention", detail, "Review large files on the root filesystem before maintenance.")
    return finding("ok", detail)


def available_memory(path=Path("/proc/meminfo")):
    try:
        values = dict(re.findall(r"^(MemTotal|MemAvailable):\s*(\d+) kB$", path.read_text(), re.MULTILINE))
        total, available = int(values["MemTotal"]), int(values["MemAvailable"])
        if not 0 <= available <= total or total == 0:
            raise ValueError
    except (OSError, KeyError, ValueError):
        return finding("unavailable", "The kernel did not report usable MemAvailable and MemTotal readings.")
    pct = 100 * available / total
    detail = f"{pct:.1f}% available ({available / 1024**2:.1f} GiB of {total / 1024**2:.1f} GiB)."
    if pct < 10:
        return finding("attention", detail, "Review memory-intensive workloads before adding maintenance load.")
    return finding("ok", detail)


def failed_services():
    try:
        result = subprocess.run(
            ["systemctl", "list-units", "--type=service", "--state=failed", "--no-legend", "--plain", "--no-pager", "--full"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, universal_newlines=True,
            timeout=5, env={**os.environ, "LC_ALL": "C"},
        )
    except (OSError, subprocess.TimeoutExpired):
        return finding("unavailable", "Could not query systemd services within five seconds.")
    if result.returncode:
        return finding("unavailable", "The system service manager could not list failed services.")
    units = [line.split()[0] for line in result.stdout.splitlines() if line.strip()]
    if any(not unit.endswith(".service") for unit in units):
        return finding("unavailable", "The system service manager returned an unrecognized unit list.")
    if not units:
        return finding("ok", "No failed systemd services reported.")
    shown = ", ".join(units[:8])
    suffix = f" and {len(units) - 8} more" if len(units) > 8 else ""
    return finding("attention", f"{len(units)} failed ({shown}{suffix}).", "Inspect the failed services before restarting workloads.")


def reboot_request(marker=Path("/run/reboot-required"), debian_version=Path("/etc/debian_version")):
    try:
        debian_version.stat()
    except FileNotFoundError:
        return finding("not_applicable", "This check uses the Debian and Ubuntu reboot-request marker.")
    except OSError:
        return finding("unavailable", "Could not determine whether the Debian reboot marker applies.")
    try:
        marker.stat()
    except FileNotFoundError:
        return finding("ok", "No reboot request recorded.")
    except OSError:
        return finding("unavailable", "Could not inspect the reboot-request marker.")
    return finding("attention", "A pending reboot is recorded.", "Schedule a reboot when workloads can be interrupted.")


if __name__ == "__main__":
    print(json.dumps({
        "root_capacity": root_capacity(),
        "memory": available_memory(),
        "services": failed_services(),
        "reboot": reboot_request(),
    }))
