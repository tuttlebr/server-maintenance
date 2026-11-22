"""Load bounded, typed result artifacts produced by completed jobs."""

from __future__ import annotations

import json
import logging
import re

from backend.config import settings

logger = logging.getLogger(__name__)

JOB_ID_RE = re.compile(r"^[0-9a-f-]{36}$")
ALLOWED_REPORT_TYPES = {"assessment", "driver", "gpu", "storage", "accounts", "packages", "services", "recovery", "kubernetes", "apt_install", "cleanup", "execution", "reboot", "discovery", "host_ip", "host_readiness"}
MAX_ARTIFACT_BYTES = 2 * 1024 * 1024


def get_job_results(job_id: str) -> list[dict]:
    if not JOB_ID_RE.fullmatch(job_id):
        return []
    result_dir = settings.data_dir / "job-results" / job_id
    if not result_dir.is_dir():
        return []

    results = []
    # Every selected host needs evidence. A count cap can hide mutation markers
    # and incorrectly classify an interrupted change as never having started.
    for path in sorted(result_dir.glob("*.json")):
        try:
            if path.stat().st_size > MAX_ARTIFACT_BYTES:
                logger.warning("Ignoring oversized job result %s", path)
                continue
            value = json.loads(path.read_text())
            if not isinstance(value, dict):
                raise ValueError("result must be an object")
            if value.get("schema_version") != 1:
                raise ValueError("unsupported schema version")
            if value.get("report_type") not in ALLOWED_REPORT_TYPES:
                raise ValueError("unsupported report type")
            if not isinstance(value.get("hostname"), str) or not value["hostname"]:
                raise ValueError("hostname is required")
            if value["report_type"] == "host_readiness":
                checks = value.get("checks")
                if not isinstance(checks, dict) or not all(
                    isinstance(checks.get(key), dict)
                    and checks[key].get("status") in {"ok", "attention", "unavailable", "not_applicable"}
                    and isinstance(checks[key].get("detail"), str) and checks[key]["detail"].strip()
                    and isinstance(checks[key].get("advice", ""), str)
                    for key in ("root_capacity", "memory", "services", "reboot")
                ):
                    raise ValueError("incomplete host readiness checks")
            results.append(value)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            logger.warning("Ignoring malformed job result %s", path, exc_info=True)
    return results
