import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


HOSTNAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,252}$")
ADDRESS_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,252}$")
LINUX_NAME_RE = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
GROUPS_RE = re.compile(r"^[a-z_][a-z0-9_-]{0,31}(,[a-z_][a-z0-9_-]{0,31})*$")
SAFE_TEXT_RE = re.compile(r"^[^{}<>\r\n$`|;]{1,120}$")
MACHINE_TYPE_VALUES = {"unknown", "dgx_spark", "dgx_workstation", "cpu_node", "gpu_node"}
MachineType = Literal["unknown", "dgx_spark", "dgx_workstation", "cpu_node", "gpu_node"]
DeviceKind = Literal["server", "workstation", "edge", "robot", "generic"]
DeviceTransport = Literal["ssh", "reachy_daemon"]
ALLOWED_SHELLS = {"/bin/bash", "/bin/sh", "/bin/zsh", "/usr/bin/bash", "/usr/bin/zsh", "/usr/sbin/nologin", "/bin/false"}
JINJA_MARKERS = ("{{", "}}", "{%", "%}", "{#", "#}")


def _strip(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip()


def _validate_hostname(value: str) -> str:
    value = value.strip()
    if not HOSTNAME_RE.fullmatch(value) or "," in value:
        raise ValueError("hostnames may only contain letters, numbers, dots, underscores, and hyphens")
    return value


def _validate_hosts(value: list[str] | None) -> list[str] | None:
    if value is None:
        return None
    deduped = []
    seen = set()
    for host in value:
        validated = _validate_hostname(host)
        if validated not in seen:
            deduped.append(validated)
            seen.add(validated)
    return deduped


def _validate_linux_name(value: str) -> str:
    value = value.strip()
    if not LINUX_NAME_RE.fullmatch(value):
        raise ValueError("must be a safe Linux account name")
    return value


def _validate_optional_linux_name(value: str | None) -> str | None:
    value = _strip(value)
    if not value:
        return None
    return _validate_linux_name(value)


def _validate_ansible_string(value: str | None, field_name: str) -> str | None:
    if value is None:
        return None
    if not value:
        return value
    if len(value) > 1024:
        raise ValueError(f"{field_name} is too long")
    if "\x00" in value or "\r" in value or "\n" in value:
        raise ValueError(f"{field_name} contains unsupported control characters")
    if any(marker in value for marker in JINJA_MARKERS):
        raise ValueError(f"{field_name} must not contain Ansible template expressions")
    return value


def _validate_account_password(value: str | None, field_name: str) -> str | None:
    value = _validate_ansible_string(value, field_name)
    if value and len(value) < 12:
        raise ValueError(f"{field_name} must be at least 12 characters")
    return value


def _validate_targeting(hosts: list[str] | None, all_hosts: bool) -> None:
    if all_hosts and hosts:
        raise ValueError("provide either hosts or all_hosts, not both")
    if not all_hosts and not hosts:
        raise ValueError("select at least one host or set all_hosts=true")


def _validate_device_targeting(device_ids: list[int] | None, all_devices: bool) -> None:
    if all_devices and device_ids:
        raise ValueError("provide either device_ids or all_devices, not both")
    if not all_devices and not device_ids:
        raise ValueError("select at least one device or set all_devices=true")


# Auth
class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=1024)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# Devices (v2 public contract)
class DeviceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=253)
    endpoint: str
    transport: DeviceTransport = "ssh"
    ssh_user: str | None = None
    ssh_password: str | None = None
    become_password: str | None = None
    bootstrap_password: str | None = None
    passwordless_ssh: bool = True
    daemon_port: int | None = Field(default=None, ge=1, le=65535)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return _validate_hostname(value)

    @field_validator("endpoint")
    @classmethod
    def validate_endpoint(cls, value: str) -> str:
        value = value.strip()
        if not ADDRESS_RE.fullmatch(value):
            raise ValueError("endpoint contains unsupported characters")
        return value

    @field_validator("ssh_user")
    @classmethod
    def validate_ssh_user(cls, value: str | None) -> str | None:
        return _validate_optional_linux_name(value)

    @field_validator("ssh_password", "become_password", "bootstrap_password")
    @classmethod
    def validate_connection_secrets(cls, value: str | None, info) -> str | None:
        return _validate_ansible_string(value, info.field_name)

    @model_validator(mode="after")
    def validate_transport_requirements(self):
        if self.transport == "ssh" and not self.ssh_user:
            raise ValueError("ssh_user is required for SSH devices")
        if self.transport == "ssh" and not self.passwordless_ssh and not self.ssh_password:
            raise ValueError("ssh_password is required when passwordless_ssh is false")
        if self.transport == "reachy_daemon" and self.daemon_port is None:
            self.daemon_port = 8000
        return self


class DeviceUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    endpoint: str | None = None
    ssh_user: str | None = None
    ssh_password: str | None = None
    become_password: str | None = None
    passwordless_ssh: bool | None = None
    daemon_port: int | None = Field(default=None, ge=1, le=65535)

    @field_validator("endpoint")
    @classmethod
    def validate_endpoint(cls, value: str | None) -> str | None:
        value = _strip(value)
        if value and not ADDRESS_RE.fullmatch(value):
            raise ValueError("endpoint contains unsupported characters")
        return value

    @field_validator("ssh_user")
    @classmethod
    def validate_ssh_user(cls, value: str | None) -> str | None:
        return _validate_optional_linux_name(value)

    @field_validator("ssh_password", "become_password")
    @classmethod
    def validate_connection_secrets(cls, value: str | None, info) -> str | None:
        return _validate_ansible_string(value, info.field_name)


class DeviceAnnotationsUpdate(BaseModel):
    annotations: dict[str, str] = Field(default_factory=dict)

    @field_validator("annotations")
    @classmethod
    def validate_annotations(cls, value: dict[str, str]) -> dict[str, str]:
        if len(value) > 50:
            raise ValueError("a device may have at most 50 manual attributes")
        cleaned: dict[str, str] = {}
        for raw_key, raw_value in value.items():
            key = str(raw_key).strip()
            item = str(raw_value).strip()
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 _./-]{0,79}", key):
                raise ValueError(f"unsupported attribute name: {key or '<empty>'}")
            if not item:
                continue
            if len(item) > 500 or "\x00" in item:
                raise ValueError(f"attribute {key} is too long or contains unsupported characters")
            cleaned[key] = item
        return cleaned


class DeviceResponse(BaseModel):
    id: int
    name: str
    inventory_name: str
    endpoint: str
    transport: str
    kind: str
    vendor: str | None = None
    model: str | None = None
    architecture: str | None = None
    os_family: str | None = None
    os_version: str | None = None
    status: str
    capabilities: list[str] = Field(default_factory=list)
    facts: dict = Field(default_factory=dict)
    annotations: dict[str, str] = Field(default_factory=dict)
    memory_gb: int | None = None
    gpu_model: str | None = None
    driver_version: str | None = None
    cuda_version: str | None = None
    nic_type: str | None = None
    nic_speed: str | None = None
    disk_root_percent: int | None = None
    disk_data_percent: int | None = None
    reboot_required: bool = False
    last_seen: datetime | None = None
    discovered_at: datetime | None = None
    created_at: datetime | None = None


class ContextDocumentResponse(BaseModel):
    id: int
    title: str
    original_filename: str
    content_type: str
    size_bytes: int
    sha256: str
    device_id: int | None = None
    device_name: str | None = None
    uploaded_by: str
    created_at: datetime


class ContextStatusResponse(BaseModel):
    record_count: int | None = None
    document_count: int = 0
    annotated_device_count: int = 0
    running: bool = False
    phase: str = "idle"
    message: str = ""
    progress: int = 0
    total: int = 0
    started_at: str | None = None
    completed_at: str | None = None
    last_indexed_at: str | None = None
    error: str | None = None


class DiscoveryResponse(BaseModel):
    reachable: bool
    trust_required: bool = False
    fingerprint: str | None = None
    kind: str = "generic"
    vendor: str | None = None
    model: str | None = None
    architecture: str | None = None
    os_family: str | None = None
    capabilities: list[str] = Field(default_factory=list)
    detail: str


class DeviceKeyApproval(BaseModel):
    fingerprint: str = Field(pattern=r"^SHA256:[A-Za-z0-9+/]{43}$")


class DeviceEnrollmentRequest(BaseModel):
    device: DeviceCreate
    approval: DeviceKeyApproval | None = None


class OperationResponse(BaseModel):
    id: str
    label: str
    description: str
    category: str
    risk: str
    confirmation: str
    icon: str
    eligible_device_ids: list[int]
    eligible_count: int


class OperationRunRequest(BaseModel):
    device_ids: list[int] = Field(min_length=1, max_length=200)

    @field_validator("device_ids")
    @classmethod
    def validate_device_ids(cls, value: list[int]) -> list[int]:
        return list(dict.fromkeys(value))


# Hosts
class HostCreate(BaseModel):
    hostname: str
    ip_address: str | None = None
    machine_type: MachineType = "unknown"
    ansible_user: str
    ansible_password: str | None = None
    ansible_become_password: str | None = None
    bootstrap_password: str | None = None
    passwordless_ssh: bool = True

    @field_validator("hostname")
    @classmethod
    def validate_hostname(cls, value: str) -> str:
        return _validate_hostname(value)

    @field_validator("ip_address")
    @classmethod
    def validate_ip_address(cls, value: str | None) -> str | None:
        value = _strip(value)
        if not value:
            return None
        if not ADDRESS_RE.fullmatch(value):
            raise ValueError("ansible host address contains unsupported characters")
        return value

    @field_validator("ansible_user")
    @classmethod
    def validate_ansible_user(cls, value: str) -> str:
        return _validate_linux_name(value)

    @field_validator("ansible_password", "ansible_become_password", "bootstrap_password")
    @classmethod
    def validate_host_passwords(cls, value: str | None, info) -> str | None:
        return _validate_ansible_string(value, info.field_name)

    @model_validator(mode="after")
    def validate_authentication(self):
        if not self.passwordless_ssh and not self.ansible_password:
            raise ValueError("ansible_password is required when passwordless_ssh is false")
        return self


class HostResponse(BaseModel):
    id: int
    hostname: str
    ip_address: str | None
    machine_type: str | None
    ansible_user: str | None
    passwordless_ssh: bool
    os_version: str | None
    gpu_model: str | None
    driver_version: str | None
    cuda_version: str | None
    memory_gb: int | None
    nic_type: str | None
    nic_speed: str | None
    fabric_manager_status: str | None
    disk_root_percent: int | None
    disk_raid_percent: int | None
    status: str
    reboot_required: bool
    last_seen: datetime | None
    created_at: datetime | None

    class Config:
        from_attributes = True


class HostUpdate(BaseModel):
    ip_address: str | None = None
    machine_type: MachineType | None = None
    ansible_user: str | None = None
    ansible_password: str | None = None
    ansible_become_password: str | None = None
    passwordless_ssh: bool | None = None

    @field_validator("ip_address")
    @classmethod
    def validate_ip_address(cls, value: str | None) -> str | None:
        value = _strip(value)
        if not value:
            return None
        if not ADDRESS_RE.fullmatch(value):
            raise ValueError("ansible host address contains unsupported characters")
        return value

    @field_validator("ansible_user")
    @classmethod
    def validate_ansible_user(cls, value: str | None) -> str | None:
        return _validate_optional_linux_name(value)

    @field_validator("ansible_password", "ansible_become_password")
    @classmethod
    def validate_host_passwords(cls, value: str | None, info) -> str | None:
        return _validate_ansible_string(value, info.field_name)

    @model_validator(mode="after")
    def validate_authentication_change(self):
        if self.passwordless_ssh is False and self.ansible_password == "":
            raise ValueError("ansible_password must not be empty when passwordless_ssh is false")
        return self


class HostKeyApproval(BaseModel):
    hostname: str
    fingerprint: str = Field(pattern=r"^SHA256:[A-Za-z0-9+/]{43}$")

    @field_validator("hostname")
    @classmethod
    def validate_hostname(cls, value: str) -> str:
        return _validate_hostname(value)


class HostEnrollmentRequest(BaseModel):
    hosts: list[HostCreate] = Field(min_length=1, max_length=200)
    approvals: list[HostKeyApproval] = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def validate_approvals(self):
        hostnames = [host.hostname for host in self.hosts]
        approved_hostnames = [approval.hostname for approval in self.approvals]
        if len(hostnames) != len(set(hostnames)):
            raise ValueError("hostnames must be unique within an enrollment request")
        if len(approved_hostnames) != len(set(approved_hostnames)):
            raise ValueError("host-key approvals must be unique by hostname")
        if set(hostnames) != set(approved_hostnames):
            raise ValueError("every enrolled host must have one matching host-key approval")
        return self


# Users
class UserInfo(BaseModel):
    full_name: str
    email: str

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value: str) -> str:
        value = value.strip()
        if not SAFE_TEXT_RE.fullmatch(value):
            raise ValueError("full name contains unsupported or shell-sensitive characters")
        return value

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not EMAIL_RE.fullmatch(value):
            raise ValueError("email address is invalid")
        username = value.split("@", 1)[0]
        _validate_linux_name(username)
        return value

    @property
    def username(self) -> str:
        return self.email.split("@", 1)[0]


class BulkUserAdd(BaseModel):
    users: list[UserInfo] = Field(min_length=1, max_length=500)
    device_ids: list[int] | None = None
    all_devices: bool = False
    password: str | None = None

    @field_validator("device_ids")
    @classmethod
    def validate_device_ids(cls, value: list[int] | None) -> list[int] | None:
        return list(dict.fromkeys(value)) if value else value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str | None) -> str | None:
        return _validate_account_password(value, "password")

    @model_validator(mode="after")
    def validate_targeting(self):
        _validate_device_targeting(self.device_ids, self.all_devices)
        return self


class BulkUserUpdate(BaseModel):
    usernames: list[str] = Field(min_length=1, max_length=500)
    device_ids: list[int] | None = None
    all_devices: bool = False
    groups: str | None = None
    shell: str | None = None

    @field_validator("usernames")
    @classmethod
    def validate_usernames(cls, value: list[str]) -> list[str]:
        return [_validate_linux_name(item) for item in value]

    @field_validator("device_ids")
    @classmethod
    def validate_device_ids(cls, value: list[int] | None) -> list[int] | None:
        return list(dict.fromkeys(value)) if value else value

    @field_validator("groups")
    @classmethod
    def validate_groups(cls, value: str | None) -> str | None:
        value = _strip(value)
        if not value:
            return None
        value = ",".join(part.strip() for part in value.split(",") if part.strip())
        if not GROUPS_RE.fullmatch(value):
            raise ValueError("groups must be a comma-separated list of safe Linux group names")
        return value

    @field_validator("shell")
    @classmethod
    def validate_shell(cls, value: str | None) -> str | None:
        value = _strip(value)
        if not value:
            return None
        if value not in ALLOWED_SHELLS:
            raise ValueError("shell is not in the allowed shell list")
        return value

    @model_validator(mode="after")
    def validate_targeting(self):
        _validate_device_targeting(self.device_ids, self.all_devices)
        if not self.groups and not self.shell:
            raise ValueError("provide at least one update field")
        return self


class ChangePasswordRequest(BaseModel):
    device_ids: list[int] | None = None
    all_devices: bool = False
    new_password: str
    force_change: bool = False

    @field_validator("device_ids")
    @classmethod
    def validate_device_ids(cls, value: list[int] | None) -> list[int] | None:
        return list(dict.fromkeys(value)) if value else value

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        return _validate_account_password(value, "new_password") or ""

    @model_validator(mode="after")
    def validate_targeting(self):
        _validate_device_targeting(self.device_ids, self.all_devices)
        return self


class BulkPasswordResetRequest(BaseModel):
    device_ids: list[int] | None = None
    all_devices: bool = False
    usernames: list[str] | None = None
    temp_password: str | None = None

    @field_validator("device_ids")
    @classmethod
    def validate_device_ids(cls, value: list[int] | None) -> list[int] | None:
        return list(dict.fromkeys(value)) if value else value

    @field_validator("usernames")
    @classmethod
    def validate_usernames(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return [_validate_linux_name(item) for item in value]

    @field_validator("temp_password")
    @classmethod
    def validate_temp_password(cls, value: str | None) -> str | None:
        return _validate_account_password(value, "temp_password")

    @model_validator(mode="after")
    def validate_targeting(self):
        _validate_device_targeting(self.device_ids, self.all_devices)
        return self


class SudoersRequest(BaseModel):
    device_ids: list[int] | None = None
    all_devices: bool = False

    @field_validator("device_ids")
    @classmethod
    def validate_device_ids(cls, value: list[int] | None) -> list[int] | None:
        return list(dict.fromkeys(value)) if value else value

    @model_validator(mode="after")
    def validate_targeting(self):
        _validate_device_targeting(self.device_ids, self.all_devices)
        return self


class RemoveUserRequest(BaseModel):
    device_ids: list[int] | None = None
    all_devices: bool = False
    remove_home: bool = False

    @field_validator("device_ids")
    @classmethod
    def validate_device_ids(cls, value: list[int] | None) -> list[int] | None:
        return list(dict.fromkeys(value)) if value else value

    @model_validator(mode="after")
    def validate_targeting(self):
        _validate_device_targeting(self.device_ids, self.all_devices)
        return self


class UserResponse(BaseModel):
    id: int
    username: str
    full_name: str | None
    email: str | None
    is_sudoer: bool
    groups: str | None
    device_ids: list[int] = Field(default_factory=list)
    created_at: datetime | None

    class Config:
        from_attributes = True


# Jobs
class JobResponse(BaseModel):
    id: int
    job_id: str
    playbook: str
    target_devices: str | None
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    duration_seconds: int | None
    triggered_by: str | None
    extra_vars: str | None
    output_log: str | None
    error_summary: str | None
    recap: str | None
    created_at: datetime | None

    class Config:
        from_attributes = True


# Drivers
class DriverUpgradeRequest(BaseModel):
    hosts: list[str] = Field(min_length=1)
    upgrade_mode: Literal["standard", "major"] = "standard"
    target_driver_version: str | None = None  # e.g. "570", "580"

    @field_validator("hosts")
    @classmethod
    def validate_hosts(cls, value: list[str]) -> list[str]:
        return _validate_hosts(value) or []


class DriverStatusResponse(BaseModel):
    hostname: str
    driver_version: str | None
    cuda_version: str | None
    machine_type: str | None
    reboot_required: bool


# Networking
class FabricManagerActionRequest(BaseModel):
    hosts: list[str] | None = None
    all_hosts: bool = False

    @field_validator("hosts")
    @classmethod
    def validate_hosts(cls, value: list[str] | None) -> list[str] | None:
        return _validate_hosts(value)

    @model_validator(mode="after")
    def validate_targeting(self):
        _validate_targeting(self.hosts, self.all_hosts)
        return self


# Maintenance
class MaintenanceRequest(BaseModel):
    hosts: list[str] | None = None
    all_hosts: bool = False

    @field_validator("hosts")
    @classmethod
    def validate_hosts(cls, value: list[str] | None) -> list[str] | None:
        return _validate_hosts(value)

    @model_validator(mode="after")
    def validate_targeting(self):
        _validate_targeting(self.hosts, self.all_hosts)
        return self


class DiskUsageResponse(BaseModel):
    hostname: str
    disk_root_percent: int | None
    disk_raid_percent: int | None


class ReportFreshness(BaseModel):
    last_scanned_at: datetime | None = None
    age_seconds: int | None = None
    stale: bool = False


class GpuUserSummary(BaseModel):
    user: str
    gpu_count: int = 0
    total_memory_mb: int = 0
    hosts: list[str] = []


class GpuHostSummary(BaseModel):
    hostname: str
    total_gpus: int = 0
    free_gpus: int = 0
    idle_gpus: int = 0
    active_gpus: int = 0
    unknown_processes: int = 0


class StorageOwnerEntry(BaseModel):
    hostname: str
    owner_user: str | None = None
    owner_uid: int | None = None
    owner_group: str | None = None
    path: str
    size_mb: int
    mountpoint: str
    mount_type: str | None = None
    use_pct: int | None = None
    kind: str | None = None


class StoragePressureHost(BaseModel):
    hostname: str
    mountpoint: str
    mount_type: str | None = None
    use_pct: int
    used_mb: int | None = None
    total_mb: int | None = None


class MaintenanceOverviewResponse(BaseModel):
    generated_at: datetime
    fleet: dict
    gpu: dict
    storage: dict


# Chat
class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=32_768)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_last_message(self):
        if self.messages[-1].role != "user":
            raise ValueError("the last chat message must have the user role")
        return self
