import json
import re
import shlex
import threading

from sqlalchemy.orm import Session

from backend.capabilities import (
    FABRIC_MANAGER_MACHINE_TYPES,
    GPU_MACHINE_TYPES,
    MACHINE_TYPES,
)
from backend.config import settings
from backend.models import Host

HOSTNAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,252}$")
ADDRESS_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,252}$")
LINUX_NAME_RE = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")
_INVENTORY_LOCK = threading.Lock()


def _ssh_common_args(passwordless_ssh: bool) -> str:
    args = [
        "-o StrictHostKeyChecking=yes",
        f"-o UserKnownHostsFile={shlex.quote(str(settings.ssh_known_hosts_file))}",
    ]
    if passwordless_ssh:
        args.extend([
            "-o PreferredAuthentications=publickey",
            "-o PasswordAuthentication=no",
        ])
    return " ".join(args)


def _validated_hostvars(h: Host) -> dict[str, str]:
    if not HOSTNAME_RE.fullmatch(h.hostname):
        raise ValueError(f"Unsafe hostname in database: {h.hostname!r}")
    if h.ip_address and not ADDRESS_RE.fullmatch(h.ip_address):
        raise ValueError(f"Unsafe address for host {h.hostname!r}")
    if h.ansible_user and not LINUX_NAME_RE.fullmatch(h.ansible_user):
        raise ValueError(f"Unsafe Ansible user for host {h.hostname!r}")

    hostvars = {
        "machine_type": h.machine_type if h.machine_type in MACHINE_TYPES else "unknown",
    }
    if h.ip_address:
        hostvars["ansible_host"] = h.ip_address
    if h.ansible_user:
        hostvars["ansible_user"] = h.ansible_user
    passwordless_ssh = not bool(h.encrypted_ansible_password)
    hostvars["ansible_ssh_common_args"] = _ssh_common_args(passwordless_ssh)
    return hostvars


def regenerate_inventory(db: Session) -> None:
    """Regenerate the Ansible inventory file from the database."""
    hosts = db.query(Host).all()
    inventory_path = settings.resolved_inventory_file

    groups: dict[str, dict[str, dict]] = {
        group_name: {"hosts": {}} for group_name in MACHINE_TYPES
    }
    for h in hosts:
        group = h.machine_type if h.machine_type in groups else "unknown"
        groups[group]["hosts"][h.hostname] = _validated_hostvars(h)

    all_machine_children = {group_name: {} for group_name in MACHINE_TYPES}
    gpu_children = {group_name: {} for group_name in GPU_MACHINE_TYPES}
    inventory = {
        "all": {
            "children": {
                **groups,
                "managed_hosts": {
                    "children": all_machine_children,
                },
                # Compatibility alias for existing playbooks. New playbooks
                # should target managed_hosts or all.
                "workstations": {
                    "children": all_machine_children,
                },
                "compute": {
                    "children": all_machine_children,
                },
                "gpu": {
                    "children": gpu_children,
                },
                "nvidia_gpu": {
                    "children": gpu_children,
                },
                "cpu": {
                    "children": {"cpu_node": {}},
                },
                "fabric_manager": {
                    "children": {
                        group_name: {} for group_name in FABRIC_MANAGER_MACHINE_TYPES
                    },
                },
            },
            "vars": {"ansible_python_interpreter": "/usr/bin/python3"},
        },
    }

    inventory_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = inventory_path.with_name(f".{inventory_path.name}.tmp")
    with _INVENTORY_LOCK:
        temporary_path.write_text(json.dumps(inventory, indent=2) + "\n")
        temporary_path.chmod(0o600)
        temporary_path.replace(inventory_path)
