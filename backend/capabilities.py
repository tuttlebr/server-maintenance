"""Capability definitions shared by discovery and operations."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable


SYSTEM_SCAN = "system.scan"
SYSTEM_ASSESS = "system.assess"
SYSTEM_BOOTSTRAP = "system.bootstrap"
SYSTEM_REBOOT = "system.reboot"
SYSTEM_UPDATE = "system.update"
STORAGE_INSPECT = "storage.inspect"
CONTAINERS_CLEANUP = "containers.cleanup"
USERS_MANAGE = "users.manage"
FIRMWARE_INSPECT = "firmware.inspect"
FIRMWARE_UPDATE = "firmware.update"
GPU_INSPECT = "gpu.inspect"
NVIDIA_DRIVER_MANAGE = "nvidia.driver.manage"
NVIDIA_FABRIC_MANAGER = "nvidia.fabric_manager.manage"
NVIDIA_MIG_MANAGE = "nvidia.mig.manage"
KUBERNETES_DRAIN = "kubernetes.drain"
REACHY_HEALTH = "reachy.health"
REACHY_DAEMON_RESTART = "reachy.daemon.restart"
REACHY_SOFTWARE_UPDATE = "reachy.software.update"
REACHY_LOGS_READ = "reachy.logs.read"
REACHY_APP_RESET = "reachy.apps.reset"
SERVICES_MANAGE = "services.manage"

BASE_LINUX_CAPABILITIES = {
    SYSTEM_SCAN,
    SYSTEM_ASSESS,
    SYSTEM_BOOTSTRAP,
    SYSTEM_REBOOT,
    STORAGE_INSPECT,
    USERS_MANAGE,
}

LEGACY_MACHINE_PROFILES = {
    "unknown": ("generic", set(BASE_LINUX_CAPABILITIES)),
    "cpu_node": (
        "server",
        BASE_LINUX_CAPABILITIES | {SYSTEM_UPDATE, CONTAINERS_CLEANUP, KUBERNETES_DRAIN},
    ),
    "gpu_node": (
        "server",
        BASE_LINUX_CAPABILITIES
        | {SYSTEM_UPDATE, CONTAINERS_CLEANUP, KUBERNETES_DRAIN, GPU_INSPECT, NVIDIA_DRIVER_MANAGE},
    ),
    "dgx_spark": (
        "edge",
        BASE_LINUX_CAPABILITIES
        | {SYSTEM_UPDATE, CONTAINERS_CLEANUP, GPU_INSPECT, NVIDIA_DRIVER_MANAGE},
    ),
    "dgx_workstation": (
        "workstation",
        BASE_LINUX_CAPABILITIES
        | {
            SYSTEM_UPDATE,
            CONTAINERS_CLEANUP,
            KUBERNETES_DRAIN,
            GPU_INSPECT,
            NVIDIA_DRIVER_MANAGE,
            NVIDIA_FABRIC_MANAGER,
            NVIDIA_MIG_MANAGE,
        },
    ),
}

def normalize_capabilities(values: Iterable[str]) -> list[str]:
    return sorted({str(value).strip() for value in values if str(value).strip()})


def legacy_profile(machine_type: str | None) -> tuple[str, list[str]]:
    kind, capabilities = LEGACY_MACHINE_PROFILES.get(
        machine_type or "unknown", LEGACY_MACHINE_PROFILES["unknown"]
    )
    return kind, normalize_capabilities(capabilities)


def device_capabilities(device) -> list[str]:
    raw = getattr(device, "capabilities_json", None)
    if raw:
        try:
            values = json.loads(raw)
            if isinstance(values, list):
                capabilities = set(normalize_capabilities(values))
                if (getattr(device, "transport", None) or "ssh") == "ssh":
                    capabilities.update(BASE_LINUX_CAPABILITIES)
                return normalize_capabilities(capabilities)
        except (TypeError, ValueError):
            pass
    return legacy_profile(getattr(device, "machine_type", None))[1]


def has_capability(device, capability: str) -> bool:
    return capability in device_capabilities(device)


@dataclass(frozen=True)
class OperationDefinition:
    id: str
    label: str
    description: str
    category: str
    required_capability: str
    risk: str
    confirmation: str
    playbook: str | None = None
    icon: str = "fa-bolt"


OPERATIONS = (
    OperationDefinition(
        SYSTEM_SCAN, "Scan devices",
        "Discover hardware, software, health, and supported capabilities before running other actions. Scan again when facts are missing or stale.",
        "Discovery", SYSTEM_SCAN, "low", "none", "host_facts.yml", "fa-magnifying-glass",
    ),
    OperationDefinition(
        "system.packages.preview", "Check for apt updates",
        "Refresh package lists and show available updates. No packages are installed.",
        "Packages", SYSTEM_UPDATE, "low", "none", "package_preview.yml", "fa-magnifying-glass",
    ),
    OperationDefinition(
        "system.update", "Install apt updates",
        "Install the checked package versions, one device at a time. Services may restart; devices are never rebooted automatically.",
        "Packages", SYSTEM_UPDATE, "high", "confirm", "system_update.yml", "fa-arrow-down",
    ),
    OperationDefinition(
        "containers.cleanup", "Clear container cache",
        "Remove unused Docker and containerd/nerdctl images and build cache. Keep containers, volumes, and networks.",
        "Containers", CONTAINERS_CLEANUP, "medium", "confirm", "docker_cleanup.yml", "fa-box",
    ),
    OperationDefinition(
        "system.reboot", "Reboot nodes",
        "Reboot every selected node, one at a time, and wait for SSH to return. Running work is interrupted; no reboot-required flag or health preflight is needed.",
        "System", SYSTEM_REBOOT, "high", "confirm", "reboot.yml", "fa-power-off",
    ),
    OperationDefinition(
        "storage.inspect", "Check storage",
        "Check capacity for the filesystem containing /home and every mount configured in /etc/fstab, including missing mounts.",
        "Storage", STORAGE_INSPECT, "low", "none", "storage_analysis.yml", "fa-hard-drive",
    ),
    OperationDefinition(
        "gpu.inspect", "Check GPU usage",
        "Show NVIDIA GPU utilization, memory, process owners, and container or pod context.",
        "GPU", GPU_INSPECT, "low", "none", "gpu_usage.yml", "fa-microchip",
    ),
    OperationDefinition(
        REACHY_DAEMON_RESTART, "Restart Reachy Mini daemon",
        "Restart the daemon on Reachy Mini devices, one at a time, and verify it returns healthy. Connected apps are interrupted and the robot may move during initialization.",
        "Reachy Mini", REACHY_DAEMON_RESTART, "high", "confirm", icon="fa-robot",
    ),
)

OPERATION_BY_ID = {operation.id: operation for operation in OPERATIONS}

def facts_are_stale(device) -> bool:
    observed = device.discovered_at
    if observed and observed.tzinfo is None:
        observed = observed.replace(tzinfo=timezone.utc)
    return bool(device.facts_stale or not observed or (datetime.now(timezone.utc) - observed).total_seconds() > 3600)


def operation_ineligibility(device, operation) -> str | None:
    if operation.id == SYSTEM_SCAN:
        return None if (device.transport or "ssh") in {"ssh", "reachy_daemon"} else "Unsupported discovery transport"
    if facts_are_stale(device):
        return "Scan devices first. Device facts are missing or stale (valid for one hour)."
    if operation.id == REACHY_DAEMON_RESTART:
        if (device.transport != "reachy_daemon" or device.kind != "robot" or
                not re.match(r"^reachy[\s_-]+mini(?:[\s_-]|$)", device.model or "", re.IGNORECASE)):
            return "Requires a Reachy Mini device connected through its daemon"
        if device.recovery_required:
            return "The previous Reachy operation needs verification. Open device settings and Scan before restarting again."
    if not has_capability(device, operation.required_capability):
        return "Required capability has not been discovered"
    if operation.id == REACHY_DAEMON_RESTART:
        return None
    if (device.transport or "ssh") != "ssh":
        return "Requires verified SSH access"
    family = device.os_family or device.facts.get("os_family")
    if operation.id in {"system.update", "system.packages.preview"} and family != "Debian":
        return "Requires apt on a Debian or Ubuntu device. Refresh device details if the OS is unknown."
    return None
