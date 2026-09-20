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
        "reachy.recover", "Verify Reachy recovery", "Check the recorded remote job and daemon health after an interrupted update or restart. Never repeats the change.",
        "Recovery", REACHY_HEALTH, "low", "none", None, "fa-stethoscope",
    ),
    OperationDefinition(
        "system.packages.preview", "Preview package updates", "Review proposed package changes without installing them. Required before applying updates.",
        "System", SYSTEM_UPDATE, "low", "none", "package_preview.yml", "fa-list-check",
    ),
    OperationDefinition(
        "services.inspect", "Inspect services", "List system services and their observed state.",
        "System", SERVICES_MANAGE, "low", "none", "service_control.yml", "fa-gears",
    ),
    OperationDefinition(
        "services.manage", "Change service state", "Start, stop, or restart one existing service and verify its state. Critical infrastructure services are protected.",
        "System", SERVICES_MANAGE, "high", "typed-target", "service_control.yml", "fa-gears",
    ),
    OperationDefinition(
        "system.recover", "Verify recovery", "Verify host health and refresh facts after interrupted maintenance. Does not roll back changes or uncordon nodes.",
        "Recovery", SYSTEM_SCAN, "low", "none", "recovery_check.yml", "fa-stethoscope",
    ),
    OperationDefinition(
        "kubernetes.drain.execute", "Drain Kubernetes node", "Cordon and evict workloads while respecting disruption budgets. Leaves the node cordoned.",
        "Orchestration", KUBERNETES_DRAIN, "high", "typed-target", "host_drain.yml", "fa-pause",
    ),
    OperationDefinition(
        "kubernetes.resume", "Resume Kubernetes node", "Verify host health and Kubernetes Ready before allowing workloads to be scheduled again.",
        "Orchestration", KUBERNETES_DRAIN, "high", "typed-target", "host_drain.yml", "fa-play",
    ),
    OperationDefinition(
        "system.scan", "Scan device", "Refresh hardware, software, storage, and health facts.",
        "Observe", SYSTEM_SCAN, "low", "none", "host_facts.yml", "fa-satellite-dish",
    ),
    OperationDefinition(
        "system.assess", "Assess maintenance readiness", "Summarize maintenance blockers, warnings, and host health.",
        "Observe", SYSTEM_ASSESS, "low", "none", "maintenance_assessment.yml", "fa-stethoscope",
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
        "system.update", "Update system packages", "Apply operating-system package updates one device at a time.",
        "System", SYSTEM_UPDATE, "high", "confirm", "system_update.yml", "fa-arrows-rotate",
    ),
    OperationDefinition(
        "system.bootstrap", "Bootstrap device", "Configure groups, passwordless administrator sudo, Docker access, and container tooling on Ubuntu. Container services may restart.",
        "System", SYSTEM_BOOTSTRAP, "high", "typed-target", "host_bootstrap.yml", "fa-wand-magic-sparkles",
    ),
    OperationDefinition(
        "containers.cleanup", "Clean container cache", "Prune unused images, cache, and networks without removing volumes.",
        "System", CONTAINERS_CLEANUP, "medium", "confirm", "docker_cleanup.yml", "fa-box",
    ),
    OperationDefinition(
        "nvidia.driver.manage", "Update NVIDIA drivers", "Update the installed NVIDIA driver branch on Debian-family devices. May reboot the device and interrupt workloads.",
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
        "firmware.inspect", "Inspect firmware", "Inventory firmware devices and available updates without changing them.",
        "Firmware", FIRMWARE_INSPECT, "low", "none", "firmware_inventory.yml", "fa-microchip",
    ),
    OperationDefinition(
        "firmware.update", "Update firmware", "Apply available firmware updates without automatically rebooting.",
        "Firmware", FIRMWARE_UPDATE, "high", "typed-target", "firmware_update.yml", "fa-download",
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
    OperationDefinition(
        "reachy.apps.reset", "Reset Reachy apps", "Delete /venvs/apps_venv so the app environment can be rebuilt. Installed apps must be reinstalled.",
        "Reachy Mini", REACHY_APP_RESET, "high", "typed-target", "reachy_app_reset.yml", "fa-eraser",
    ),
)

OPERATION_BY_ID = {operation.id: operation for operation in OPERATIONS}

MAINTENANCE_OPERATIONS = {
    "system.reboot", "system.update", "system.bootstrap", "nvidia.driver.manage",
    "firmware.update", "services.manage", "kubernetes.drain.execute", "kubernetes.resume",
}
RECOVERY_OPERATIONS = {"system.recover", "kubernetes.resume"}


def facts_are_stale(device) -> bool:
    observed = device.discovered_at
    if observed and observed.tzinfo is None:
        observed = observed.replace(tzinfo=timezone.utc)
    return bool(device.facts_stale or not observed or (datetime.now(timezone.utc) - observed).total_seconds() > 3600)


def operation_ineligibility(device, operation) -> str | None:
    if not has_capability(device, operation.required_capability):
        return "Required capability has not been discovered"
    if device.recovery_required and operation.risk != "low" and operation.id not in RECOVERY_OPERATIONS:
        return "Verify recovery before making another change"
    if operation.id.startswith("reachy."):
        return None
    if (device.transport or "ssh") != "ssh":
        return "Requires verified SSH access"
    facts = device.facts
    family = device.os_family or facts.get("os_family")
    if operation.risk != "low" and family not in {"Debian", "RedHat", "Suse", "Archlinux", "Alpine", "Gentoo"}:
        return "Requires a discovered supported Linux platform"
    if operation.id in {"system.update", "system.packages.preview"} and family not in {"Debian", "RedHat"}:
        return "Package updates support discovered Debian and Red Hat family devices"
    if operation.id == "system.bootstrap" and facts.get("distribution") != "Ubuntu":
        return "Bootstrap supports discovered Ubuntu devices only"
    if operation.id == "nvidia.driver.manage":
        package = facts.get("nvidia_driver_package") or ""
        if family != "Debian" or not re.fullmatch(r"nvidia-driver-\d+(?:-server)?(?:-open)?", package):
            return "Requires a discovered supported Debian NVIDIA driver metapackage"
    if operation.id.startswith("services.") and facts.get("service_manager") != "systemd":
        return "Requires discovered systemd services"
    if operation.id in MAINTENANCE_OPERATIONS:
        if device.maintenance_mode not in {"standalone", "kubernetes"}:
            return "Configure standalone or Kubernetes maintenance mode on the device"
        if operation.id.startswith("kubernetes.") and device.maintenance_mode != "kubernetes":
            return "Configure the device's Kubernetes context and node"
    if operation.risk != "low" and operation.id not in RECOVERY_OPERATIONS:
        if facts_are_stale(device):
            return "Run a fresh scan before changing this device (facts must be under one hour old)"
    return None
