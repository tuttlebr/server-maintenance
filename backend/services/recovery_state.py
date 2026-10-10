"""Repair legacy recovery flags only when completed logs prove no change began."""

import json
import logging
import re
from datetime import datetime, timezone

from backend.models import Device, DeviceReservation, Job
from backend.services.execution_state import ACTIVE_STATUSES, parse_host_outcomes
from backend.services.job_results import get_job_results

logger = logging.getLogger(__name__)

# Known tasks before the first possible mutation in the old and current plays.
# In particular, Kubernetes preparation is NOT safe: a failed drain can cordon
# a node even when Ansible reports changed=0.
PREFLIGHT_TASKS = {
    "system_update.yml": {
        "Gathering Facts", "Validate supported package manager",
        "Preview Debian package changes", "Preview Red Hat package changes",
        "Normalize the proposed transaction", "Fingerprint the proposed transaction",
        "Pin the exact proposed package versions",
        "Require apt on a Debian family device",
        "Simulate apt updates without removing packages",
        "Normalize package names and candidate versions", "Fingerprint exact package versions",
        "Require a matching reviewed package preview",
    },
    "docker_cleanup.yml": {
        "Gathering Facts", "Check if Docker CLI is installed",
        "Check whether Docker is running", "Check if nerdctl is installed",
        "Check whether containerd is running",
        "Require at least one available container runtime",
    },
}
SOURCE_REASON = re.compile(r"Incomplete job ([0-9a-f-]{36}) \((system_update\.yml|docker_cleanup\.yml)\)")
TASK = re.compile(r"^(?:TASK|RUNNING HANDLER) \[(.+)\] \*+")
EVENT = re.compile(r"^(ok|changed|fatal): \[([^\] ]+)(?:[^\]]*)\]")


def preflight_failures(job):
    """Return evidence per host, never infer safety from age or changed=0 alone."""
    if (job.playbook not in PREFLIGHT_TASKS or job.phase != "complete"
            or job.status not in {"failed", "partial", "recovery_required"} or not job.finished_at):
        return {}
    output = job.output_log or ""
    if "timed out" in (output + (job.error_summary or "")).lower():
        return {}
    # Use only the operation's log. A successful subsequent scan cannot prove
    # that the preceding operation made no changes.
    output = output.partition("--- Post-operation facts ---")[0]
    if not re.search(r"^PLAY \[", output, re.MULTILINE) or not re.search(r"^PLAY RECAP\b", output, re.MULTILINE):
        return {}
    targets = [name for name in (job.target_hosts or "").split(",") if name]
    outcomes = parse_host_outcomes(output, targets)
    events = {}
    task = None
    for line in output.splitlines():
        match = TASK.match(line)
        if match:
            task = match[1]
        match = EVENT.match(line)
        if match:
            events.setdefault(match[2], []).append((task, match[1]))
    # Any report from the mutation/recovery stages overrides log inference.
    started = {r["hostname"] for r in get_job_results(job.job_id)
               if r["report_type"] in {"execution", "kubernetes", "apt_install", "cleanup"}}
    safe = {}
    for outcome in outcomes:
        name = outcome["hostname"]
        observed = events.get(name, [])
        first_tasks = {"Gathering Facts"} if job.playbook == "system_update.yml" else {"Gathering Facts", "Check if Docker CLI is installed"}
        if (name in started or not observed or observed[0][0] not in first_tasks
                or outcome.get("changed") != 0 or outcome["status"] not in {"failed", "unreachable"}
                or observed[-1][1] != "fatal"
                or any(title not in PREFLIGHT_TASKS[job.playbook] or state == "changed" for title, state in observed)):
            continue
        safe[name] = f"Stopped at '{observed[-1][0]}' before any device changes."
    # Serial execution can stop before reaching the remaining targets. Only
    # infer this when EVERY observed host failed in the known read-only prefix.
    recapped = {item["hostname"] for item in outcomes if "changed" in item}
    if recapped and recapped == set(safe) and set(events) == recapped and not started:
        for name in set(targets) - recapped:
            safe[name] = "The job stopped during preflight before reaching this device."
    return safe


def reconcile_stale_recovery(db):
    """Run with the startup executor lease, before accepting new requests."""
    reserved = {row.device_id for row in db.query(DeviceReservation).all()}
    active = {name for job in db.query(Job).filter(Job.status.in_(ACTIVE_STATUSES)).all()
              for name in (job.target_hosts or "").split(",")}
    jobs = {}
    cleared = []
    for device in db.query(Device).filter_by(recovery_required=True).all():
        if device.id in reserved or device.hostname in active:
            continue
        match = SOURCE_REASON.fullmatch(device.recovery_reason or "")
        if not match:
            continue
        job_id, playbook = match.groups()
        if job_id not in jobs:
            job = db.query(Job).filter_by(job_id=job_id, playbook=playbook).first()
            jobs[job_id] = (job, preflight_failures(job) if job else {})
        job, evidence = jobs[job_id]
        if device.hostname not in evidence:
            continue
        device.recovery_required = False
        device.recovery_reason = None
        # Keep inventory freshness independent from recovery; no facts were read.
        results = {item["hostname"]: item for item in job.device_results}
        result = results.setdefault(device.hostname, {"hostname": device.hostname, "status": "not_checked"})
        result["recovery_resolution"] = evidence[device.hostname]
        result["recovery_resolved_at"] = datetime.now(timezone.utc).isoformat()
        job.outcomes_json = json.dumps(list(results.values()))
        cleared.append(device.hostname)
        logger.info("Cleared stale recovery flag for %s from job %s: %s", device.hostname, job_id, evidence[device.hostname])
    for job, evidence in jobs.values():
        if not job or not evidence:
            continue
        outcomes = {item["hostname"]: item for item in job.device_results}
        unresolved = [name for name in (job.target_hosts or "").split(",")
                      if not outcomes.get(name, {}).get("recovery_resolution")
                      and outcomes.get(name, {}).get("status") != "success"]
        if not unresolved and job.status == "recovery_required":
            job.status = "partial" if any(item.get("status") == "success" for item in outcomes.values()) else "failed"
    db.commit()
    return cleared
