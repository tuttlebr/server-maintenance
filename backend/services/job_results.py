"""Load bounded, typed result artifacts produced by completed jobs."""

from __future__ import annotations

import json
import logging
import re

from backend.config import settings

logger = logging.getLogger(__name__)

JOB_ID_RE = re.compile(r"^[0-9a-f-]{36}$")
ALLOWED_REPORT_TYPES = {"assessment", "driver", "gpu", "storage"}
MAX_ARTIFACTS_PER_JOB = 200
MAX_ARTIFACT_BYTES = 2 * 1024 * 1024


def get_job_results(job_id: str) -> list[dict]:
    if not JOB_ID_RE.fullmatch(job_id):
        return []
    result_dir = settings.data_dir / "job-results" / job_id
    if not result_dir.is_dir():
        return []

    results = []
    for path in sorted(result_dir.glob("*.json"))[:MAX_ARTIFACTS_PER_JOB]:
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
            results.append(value)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            logger.warning("Ignoring malformed job result %s", path, exc_info=True)
    return results
