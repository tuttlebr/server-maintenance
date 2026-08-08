"""Device discovery and enrichment without vendor-shaped UI assumptions."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from backend.capabilities import (
    BASE_LINUX_CAPABILITIES,
    CONTAINERS_CLEANUP,
    GPU_INSPECT,
    KUBERNETES_DRAIN,
    NVIDIA_DRIVER_MANAGE,
    NVIDIA_FABRIC_MANAGER,
    NVIDIA_MIG_MANAGE,
    REACHY_DAEMON_RESTART,
    REACHY_HEALTH,
    REACHY_LOGS_READ,
    REACHY_SOFTWARE_UPDATE,
    SYSTEM_UPDATE,
    legacy_profile,
    normalize_capabilities,
)


def initial_profile(transport: str, legacy_machine_type: str | None = None) -> dict:
    if transport == "reachy_daemon":
        return {
            "kind": "robot",
            "vendor": "Pollen Robotics",
            "model": "Reachy Mini Wireless",
            "capabilities": normalize_capabilities(
                {
                    REACHY_HEALTH,
                    REACHY_LOGS_READ,
                    REACHY_DAEMON_RESTART,
                    REACHY_SOFTWARE_UPDATE,
                }
            ),
        }
    kind, capabilities = legacy_profile(legacy_machine_type)
    return {"kind": kind, "vendor": None, "model": None, "capabilities": capabilities}


def probe_reachy(endpoint: str, port: int = 8000, timeout: float = 3.0) -> dict:
    try:
        robot_state = reachy_request(endpoint, port, "/api/state/full", timeout=timeout)
        facts = {"robot_state": robot_state}
        try:
            facts["daemon"] = reachy_request(
                endpoint, port, "/api/daemon/status", timeout=timeout
            )
        except RuntimeError:
            pass
        try:
            facts["software"] = reachy_request(
                endpoint, port, "/update/available", timeout=max(timeout, 5.0)
            )
        except RuntimeError:
            pass
        return {
            "reachable": True,
            "detail": "Reachy Mini daemon responded without moving the robot.",
            "facts": facts,
            **initial_profile("reachy_daemon"),
        }
    except RuntimeError as exc:
        return {
            "reachable": False,
            "detail": f"Reachy Mini daemon did not respond: {exc}",
            "facts": {},
            **initial_profile("reachy_daemon"),
        }


def reachy_request(
    endpoint: str,
    port: int,
    path: str,
    *,
    method: str = "GET",
    query: dict[str, str] | None = None,
    timeout: float = 5.0,
) -> dict:
    """Call a documented, non-motion Reachy daemon endpoint."""
    host = f"[{endpoint}]" if ":" in endpoint and not endpoint.startswith("[") else endpoint
    query_string = f"?{urllib.parse.urlencode(query)}" if query else ""
    url = f"http://{host}:{port}{path}{query_string}"
    request = urllib.request.Request(
        url,
        method=method,
        headers={"Accept": "application/json"},
        data=b"" if method != "GET" else None,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
        payload = json.loads(body) if body else {}
        if not isinstance(payload, dict):
            raise ValueError("expected a JSON object")
        return payload
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read().decode("utf-8")).get("detail")
        except (ValueError, AttributeError, json.JSONDecodeError):
            detail = None
        raise RuntimeError(f"Reachy daemon returned HTTP {exc.code}: {detail or exc.reason}") from exc
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Reachy daemon request failed: {exc}") from exc


def reachy_websocket_url(endpoint: str, port: int, path: str) -> str:
    host = f"[{endpoint}]" if ":" in endpoint and not endpoint.startswith("[") else endpoint
    return f"ws://{host}:{port}{path}"


def enrich_from_scan(device, report: dict) -> None:
    """Update identity and capabilities from portable scan facts."""
    capabilities = set(BASE_LINUX_CAPABILITIES)
    capabilities.update({SYSTEM_UPDATE, CONTAINERS_CLEANUP})
    if report.get("kubernetes_available") is True:
        capabilities.add(KUBERNETES_DRAIN)

    gpu_model = str(report.get("gpu_model") or "").strip()
    if gpu_model and gpu_model.lower() not in {"unknown", "n/a"}:
        capabilities.add(GPU_INSPECT)
        if "nvidia" in str(report.get("gpu_vendor") or "nvidia").lower():
            capabilities.add(NVIDIA_DRIVER_MANAGE)

    if report.get("fabric_manager_available") is True:
        capabilities.add(NVIDIA_FABRIC_MANAGER)
    if report.get("mig_available") is True:
        capabilities.add(NVIDIA_MIG_MANAGE)

    vendor = _clean_fact(report.get("system_vendor"))
    model = _clean_fact(report.get("product_name"))
    architecture = _clean_fact(report.get("architecture"))
    os_family = _clean_fact(report.get("os_family"))

    if gpu_model and "nvidia" in str(report.get("gpu_vendor") or "nvidia").lower():
        vendor = vendor or "NVIDIA"

    device.vendor = vendor
    device.model = model
    device.architecture = architecture
    device.os_family = os_family
    device.kind = infer_kind(vendor, model, architecture, device.kind)
    # Keep the old value only as a private playbook tuning hint while the
    # public model remains kind + capabilities. This lets existing NVIDIA
    # playbooks choose platform-specific package paths after discovery.
    combined = f"{vendor or ''} {model or ''}".lower()
    if "dgx spark" in combined:
        device.machine_type = "dgx_spark"
    elif "dgx" in combined or device.kind == "workstation":
        device.machine_type = "dgx_workstation" if "dgx" in combined else (
            "gpu_node" if GPU_INSPECT in capabilities else "cpu_node"
        )
    else:
        device.machine_type = "gpu_node" if GPU_INSPECT in capabilities else "cpu_node"
    device.capabilities = normalize_capabilities(capabilities)
    device.facts = {
        "system_vendor": vendor,
        "product_name": model,
        "architecture": architecture,
        "os_family": os_family,
        "secure_boot": report.get("secure_boot"),
        "firmware": report.get("firmware_info"),
    }
    device.discovered_at = datetime.now(timezone.utc)


def infer_kind(
    vendor: str | None,
    model: str | None,
    architecture: str | None,
    current: str | None = None,
) -> str:
    combined = f"{vendor or ''} {model or ''}".lower()
    if "reachy" in combined:
        return "robot"
    if "dgx spark" in combined or "jetson" in combined:
        return "edge"
    if "workstation" in combined or "station" in combined:
        return "workstation"
    if any(value in combined for value in ("server", "poweredge", "proliant", "dgx")):
        return "server"
    if architecture and architecture.lower() in {"aarch64", "arm64"}:
        return "edge"
    return current if current in {"server", "workstation", "edge", "robot"} else "generic"


def _clean_fact(value) -> str | None:
    text = str(value or "").strip()
    if not text or text.lower() in {"unknown", "none", "n/a", "not specified"}:
        return None
    return text[:160]
