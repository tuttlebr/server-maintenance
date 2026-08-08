import json
import re
import shlex
import threading

from sqlalchemy.orm import Session

from backend.capabilities import (
    GPU_INSPECT,
    NVIDIA_DRIVER_MANAGE,
    NVIDIA_FABRIC_MANAGER,
    NVIDIA_MIG_MANAGE,
    has_capability,
)
from backend.config import settings
from backend.models import Device

HOSTNAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,252}$")
ADDRESS_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,252}$")
LINUX_NAME_RE = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")
DEVICE_KINDS = ("generic", "server", "workstation", "edge", "robot")
LEGACY_TYPES = ("unknown", "cpu_node", "gpu_node", "dgx_spark", "dgx_workstation")
_INVENTORY_LOCK = threading.Lock()


def _ssh_common_args(passwordless_ssh: bool) -> str:
    args = [
        "-o StrictHostKeyChecking=yes",
        f"-o UserKnownHostsFile={shlex.quote(str(settings.ssh_known_hosts_file))}",
    ]
    if passwordless_ssh:
        args.extend(["-o PreferredAuthentications=publickey", "-o PasswordAuthentication=no"])
    return " ".join(args)


def _validated_device_vars(device: Device) -> dict[str, str]:
    if not HOSTNAME_RE.fullmatch(device.hostname):
        raise ValueError(f"Unsafe inventory name in database: {device.hostname!r}")
    endpoint = getattr(device, "endpoint", None) or getattr(device, "ip_address", None)
    if endpoint and not ADDRESS_RE.fullmatch(endpoint):
        raise ValueError(f"Unsafe endpoint for device {device.hostname!r}")
    if device.ansible_user and not LINUX_NAME_RE.fullmatch(device.ansible_user):
        raise ValueError(f"Unsafe SSH user for device {device.hostname!r}")

    legacy_type = getattr(device, "machine_type", None)
    if legacy_type not in LEGACY_TYPES:
        legacy_type = "unknown"
    hostvars = {
        "device_kind": getattr(device, "kind", None) or "generic",
        "machine_type": legacy_type,
    }
    if endpoint:
        hostvars["ansible_host"] = endpoint
    if device.ansible_user:
        hostvars["ansible_user"] = device.ansible_user
    hostvars["ansible_ssh_common_args"] = _ssh_common_args(not bool(device.encrypted_ansible_password))
    return hostvars


def regenerate_inventory(db: Session) -> None:
    """Generate capability groups for SSH-managed devices."""
    devices = sorted(db.query(Device).all(), key=lambda device: device.hostname)
    groups: dict[str, dict] = {kind: {"hosts": {}} for kind in DEVICE_KINDS}
    groups.update({
        "managed_hosts": {"hosts": {}},
        "compute": {"hosts": {}},
        "gpu": {"hosts": {}},
        "nvidia_gpu": {"hosts": {}},
        "fabric_manager": {"hosts": {}},
        "mig": {"hosts": {}},
        "cpu": {"hosts": {}},
    })

    # Temporary compatibility groups for playbook conditions that still apply
    # vendor-specific tuning after capability eligibility has been checked.
    for legacy in LEGACY_TYPES:
        groups[legacy] = {"hosts": {}}

    for device in devices:
        if (getattr(device, "transport", None) or "ssh") != "ssh":
            continue
        hostvars = _validated_device_vars(device)
        name = device.hostname
        device_kind = getattr(device, "kind", None)
        kind = device_kind if device_kind in DEVICE_KINDS else "generic"
        groups[kind]["hosts"][name] = hostvars
        groups["managed_hosts"]["hosts"][name] = hostvars
        groups["compute"]["hosts"][name] = hostvars
        legacy = device.machine_type if device.machine_type in groups else "unknown"
        groups[legacy]["hosts"][name] = hostvars
        if has_capability(device, GPU_INSPECT):
            groups["gpu"]["hosts"][name] = hostvars
        else:
            groups["cpu"]["hosts"][name] = hostvars
        if has_capability(device, NVIDIA_DRIVER_MANAGE):
            groups["nvidia_gpu"]["hosts"][name] = hostvars
        if has_capability(device, NVIDIA_FABRIC_MANAGER):
            groups["fabric_manager"]["hosts"][name] = hostvars
        if has_capability(device, NVIDIA_MIG_MANAGE):
            groups["mig"]["hosts"][name] = hostvars

    inventory = {
        "all": {
            "children": groups,
            # Mixed fleets often have a newer automation-compatible Python
            # alongside an OS-owned /usr/bin/python3. Let Ansible select the
            # best supported interpreter for each device.
            "vars": {"ansible_python_interpreter": "auto_silent"},
        }
    }
    inventory_path = settings.resolved_inventory_file
    inventory_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = inventory_path.with_name(f".{inventory_path.name}.tmp")
    with _INVENTORY_LOCK:
        temporary_path.write_text(json.dumps(inventory, indent=2) + "\n")
        temporary_path.chmod(0o600)
        temporary_path.replace(inventory_path)


# Compatibility name used by security unit tests and older imports.
_validated_hostvars = _validated_device_vars
