"""Capability definitions shared by discovery, operations, and legacy playbooks."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterable


SYSTEM_SCAN = "system.scan"
SYSTEM_REBOOT = "system.reboot"
SYSTEM_UPDATE = "system.update"
STORAGE_INSPECT = "storage.inspect"
CONTAINERS_CLEANUP = "containers.cleanup"
USERS_MANAGE = "users.manage"
GPU_INSPECT = "gpu.inspect"
NVIDIA_DRIVER_MANAGE = "nvidia.driver.manage"
NVIDIA_FABRIC_MANAGER = "nvidia.fabric_manager.manage"
NVIDIA_MIG_MANAGE = "nvidia.mig.manage"
KUBERNETES_DRAIN = "kubernetes.drain"
REACHY_HEALTH = "reachy.health"
REACHY_DAEMON_RESTART = "reachy.daemon.restart"
REACHY_SOFTWARE_UPDATE = "reachy.software.update"
REACHY_LOGS_READ = "reachy.logs.read"

BASE_LINUX_CAPABILITIES = {
    SYSTEM_SCAN,
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

# Compatibility constants used only by playbook-specific v1 implementation
# modules. New code must call has_capability().
MACHINE_TYPES = tuple(LEGACY_MACHINE_PROFILES)
GPU_MACHINE_TYPES = tuple(
    name for name, (_, capabilities) in LEGACY_MACHINE_PROFILES.items() if GPU_INSPECT in capabilities
)
FABRIC_MANAGER_MACHINE_TYPES = tuple(
    name for name, (_, capabilities) in LEGACY_MACHINE_PROFILES.items() if NVIDIA_FABRIC_MANAGER in capabilities
)


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
                return normalize_capabilities(values)
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
        "system.scan", "Scan device", "Refresh hardware, software, storage, and health facts.",
        "Observe", SYSTEM_SCAN, "low", "none", "host_facts.yml", "fa-satellite-dish",
    ),
    OperationDefinition(
        "storage.inspect", "Analyze storage", "Find filesystem pressure and large directory owners.",
        "Observe", STORAGE_INSPECT, "low", "none", "storage_analysis.yml", "fa-hard-drive",
    ),
    OperationDefinition(
        "gpu.inspect", "Inspect GPU usage", "Report GPU utilization, memory, processes, and owners.",
        "Observe", GPU_INSPECT, "low", "none", "gpu_usage.yml", "fa-microchip",
    ),
    OperationDefinition(
        "system.reboot", "Reboot", "Restart selected devices one at a time after safety checks.",
        "System", SYSTEM_REBOOT, "high", "typed-target", "reboot.yml", "fa-power-off",
    ),
    OperationDefinition(
        "containers.cleanup", "Clean container cache", "Prune unused images, cache, and networks without removing volumes.",
        "System", CONTAINERS_CLEANUP, "medium", "confirm", "docker_cleanup.yml", "fa-box",
    ),
    OperationDefinition(
        "nvidia.driver.manage", "Update NVIDIA drivers", "Apply a patch-level NVIDIA driver update.",
        "NVIDIA", NVIDIA_DRIVER_MANAGE, "high", "confirm", "driver_upgrade.yml", "fa-microchip",
    ),
    OperationDefinition(
        "nvidia.fabric_manager.manage", "Check Fabric Manager", "Check NVLink and NVSwitch fabric service state.",
        "NVIDIA", NVIDIA_FABRIC_MANAGER, "low", "none", "fabric_manager.yml", "fa-network-wired",
    ),
    OperationDefinition(
        "nvidia.mig.manage", "Check MIG mode", "Query NVIDIA Multi-Instance GPU mode without changing it.",
        "NVIDIA", NVIDIA_MIG_MANAGE, "low", "none", "mig_management.yml", "fa-layer-group",
    ),
    OperationDefinition(
        "kubernetes.drain", "Check Kubernetes readiness", "Inspect active work and node schedulability.",
        "Orchestration", KUBERNETES_DRAIN, "low", "none", "host_drain.yml", "fa-diagram-project",
    ),
    OperationDefinition(
        "reachy.health", "Check Reachy health", "Read daemon connectivity and current robot state without moving it.",
        "Reachy Mini", REACHY_HEALTH, "low", "none", None, "fa-robot",
    ),
    OperationDefinition(
        "reachy.logs.read", "Collect Reachy logs", "Collect recent daemon logs for troubleshooting.",
        "Reachy Mini", REACHY_LOGS_READ, "low", "none", None, "fa-file-lines",
    ),
    OperationDefinition(
        "reachy.daemon.restart", "Restart Reachy daemon", "Restart robot software without waking or moving the robot.",
        "Reachy Mini", REACHY_DAEMON_RESTART, "high", "confirm", None, "fa-rotate",
    ),
    OperationDefinition(
        "reachy.software.update", "Update Reachy software", "Install the latest stable Reachy Mini software through its daemon.",
        "Reachy Mini", REACHY_SOFTWARE_UPDATE, "high", "confirm", None, "fa-cloud-arrow-down",
    ),
)

OPERATION_BY_ID = {operation.id: operation for operation in OPERATIONS}
