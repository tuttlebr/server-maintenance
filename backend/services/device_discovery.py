"""Device discovery and enrichment without vendor-shaped UI assumptions."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from backend.capabilities import (
    BASE_LINUX_CAPABILITIES,
    CONTAINERS_CLEANUP,
    FIRMWARE_INSPECT,
    FIRMWARE_UPDATE,
    GPU_INSPECT,
    KUBERNETES_DRAIN,
    NVIDIA_DRIVER_MANAGE,
    NVIDIA_FABRIC_MANAGER,
    NVIDIA_MIG_MANAGE,
    REACHY_DAEMON_RESTART,
    REACHY_APP_RESET,
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
    if report.get("firmware_tool_available") is True:
        capabilities.add(FIRMWARE_INSPECT)
    if report.get("firmware_update_available") is True:
        capabilities.add(FIRMWARE_UPDATE)
    if report.get("reachy_mini_available") is True:
        capabilities.add(REACHY_APP_RESET)

    vendor = _clean_fact(report.get("system_vendor"))
    model = _clean_fact(report.get("product_name"))
    architecture = _clean_fact(report.get("architecture"))
    os_family = _clean_fact(report.get("os_family"))
    dgx_name = _clean_fact(report.get("dgx_name"))
    dgx_pretty_name = _clean_fact(report.get("dgx_pretty_name"))
    dgx_platform = _clean_fact(report.get("dgx_platform"))
    dgx_swbuild_version = _clean_fact(report.get("dgx_swbuild_version"))

    if gpu_model and "nvidia" in str(report.get("gpu_vendor") or "nvidia").lower():
        vendor = vendor or "NVIDIA"

    is_dgx_spark = _is_dgx_spark(
        report,
        model=model,
        architecture=architecture,
        gpu_model=gpu_model,
    )

    if report.get("reachy_mini_available") is True:
        vendor = vendor or "Pollen Robotics"
        model = "Reachy Mini Wireless"

    device.vendor = vendor
    device.model = model
    device.architecture = architecture
    device.os_family = os_family
    device.kind = (
        "edge" if is_dgx_spark else infer_kind(vendor, model, architecture, device.kind)
    )
    # Keep the old value only as a private playbook tuning hint while the
    # public model remains kind + capabilities. This lets existing NVIDIA
    # playbooks choose platform-specific package paths after discovery.
    if is_dgx_spark:
        device.machine_type = "dgx_spark"
    elif _is_dgx_product(model) or device.kind == "workstation":
        device.machine_type = "dgx_workstation" if _is_dgx_product(model) else (
            "gpu_node" if GPU_INSPECT in capabilities else "cpu_node"
        )
    else:
        device.machine_type = "gpu_node" if GPU_INSPECT in capabilities else "cpu_node"
    device.capabilities = normalize_capabilities(capabilities)
    facts = {
        "system_vendor": vendor,
        "product_name": model,
        "product_version": _clean_fact(report.get("product_version")),
        "architecture": architecture,
        "os_family": os_family,
        "motherboard": {
            "vendor": _clean_fact(report.get("motherboard_vendor")),
            "model": _clean_fact(report.get("motherboard_model")),
            "version": _clean_fact(report.get("motherboard_version")),
        },
        "bios": {
            "vendor": _clean_fact(report.get("bios_vendor")),
            "version": _clean_fact(report.get("bios_version")),
            "date": _clean_fact(report.get("bios_date")),
        },
        "cpu": {
            "model": _clean_fact(report.get("cpu_model")),
            "sockets": _clean_number(report.get("cpu_sockets")),
            "cores_per_socket": _clean_number(report.get("cpu_cores")),
            "vcpus": _clean_number(report.get("cpu_vcpus")),
        },
        "kernel": _clean_fact(report.get("kernel")),
        "virtualization": _clean_fact(report.get("virtualization_type")),
        "network": {
            "primary_interface": _clean_fact(report.get("primary_interface")),
            "interfaces": report.get("network_interfaces") if isinstance(report.get("network_interfaces"), list) else [],
        },
        "storage_mounts": report.get("storage_mounts") if isinstance(report.get("storage_mounts"), list) else [],
        "secure_boot": report.get("secure_boot"),
        "firmware": report.get("firmware_info"),
        "firmware_tool_available": report.get("firmware_tool_available") is True,
        "firmware_update_available": report.get("firmware_update_available") is True,
        "reachy_mini_available": report.get("reachy_mini_available") is True,
    }
    dgx_facts = {
        "name": dgx_name or ("DGX Spark" if is_dgx_spark else None),
        "pretty_name": dgx_pretty_name,
        "platform": dgx_platform,
        "swbuild_version": dgx_swbuild_version,
    }
    if any(dgx_facts.values()):
        facts["dgx"] = dgx_facts
    device.facts = facts
    device.discovered_at = datetime.now(timezone.utc)


def _is_dgx_spark(
    report: dict,
    *,
    model: str | None,
    architecture: str | None,
    gpu_model: str,
) -> bool:
    """Identify branded and OEM DGX Spark systems without broad DGX matching."""
    if (architecture or "").lower() not in {"aarch64", "arm64"}:
        return False

    release_name = _normalize_identity(report.get("dgx_name"))
    release_pretty_name = _normalize_identity(report.get("dgx_pretty_name"))
    model_name = _normalize_identity(model)
    if (
        release_name == "dgx spark"
        or release_pretty_name == "nvidia dgx spark"
        or model_name in {"dgx spark", "nvidia dgx spark"}
    ):
        return True

    gpu_vendor = str(report.get("gpu_vendor") or "").lower()
    gpu_tokens = _fact_tokens(gpu_model)
    if "gb10" not in gpu_tokens or (
        "nvidia" not in gpu_vendor and "nvidia" not in gpu_model.lower()
    ):
        return False

    platform_tokens: set[str] = set()
    for value in (
        report.get("dgx_platform"),
        model,
        report.get("product_version"),
        report.get("motherboard_model"),
    ):
        platform_tokens.update(_fact_tokens(value))
    return bool(platform_tokens & {"gx10", "gx10dgx"})


def infer_kind(
    vendor: str | None,
    model: str | None,
    architecture: str | None,
    current: str | None = None,
) -> str:
    combined = f"{vendor or ''} {model or ''}".lower()
    model_name = _normalize_identity(model)
    if "reachy" in combined:
        return "robot"
    if model_name in {"dgx spark", "nvidia dgx spark"} or "jetson" in combined:
        return "edge"
    if "workstation" in combined or "station" in combined:
        return "workstation"
    if any(
        value in combined for value in ("server", "poweredge", "proliant")
    ) or _is_dgx_product(model):
        return "server"
    if architecture and architecture.lower() in {"aarch64", "arm64"}:
        return "edge"
    return current if current in {"server", "workstation", "edge", "robot"} else "generic"


def _clean_fact(value) -> str | None:
    text = str(value or "").strip()
    if not text or text.lower() in {"unknown", "none", "n/a", "not specified"}:
        return None
    return text[:160]


def _fact_tokens(value) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", str(value or "").lower()))


def _normalize_identity(value) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _is_dgx_product(model) -> bool:
    model_name = _normalize_identity(model)
    return (
        model_name == "dgx"
        or model_name.startswith("dgx ")
        or model_name.startswith("nvidia dgx ")
    )


def _clean_number(value) -> int | None:
    try:
        number = int(value)
        return number if number >= 0 else None
    except (TypeError, ValueError):
        return None
