import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


HOSTNAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,252}$")
ADDRESS_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,252}$")
LINUX_NAME_RE = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
GROUPS_RE = re.compile(r"^[a-z_][a-z0-9_-]{0,31}(,[a-z_][a-z0-9_-]{0,31})*$")
SAFE_TEXT_RE = re.compile(r"^[^{}<>\r\n$`|;]{1,120}$")
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
    ssh_user: str | None = None
    passwordless_ssh: bool = True
    daemon_port: int | None = None
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


class DeviceSshEnrollmentRequest(BaseModel):
    ssh_user: str
    ssh_password: str | None = None
    become_password: str | None = None
    bootstrap_password: str | None = None
    passwordless_ssh: bool = True
    approval: DeviceKeyApproval

    @field_validator("ssh_user")
    @classmethod
    def validate_ssh_user(cls, value: str) -> str:
        return _validate_linux_name(value)

    @field_validator("ssh_password", "become_password", "bootstrap_password")
    @classmethod
    def validate_connection_secrets(cls, value: str | None, info) -> str | None:
        return _validate_ansible_string(value, info.field_name)

    @model_validator(mode="after")
    def validate_authentication(self):
        if not self.passwordless_ssh and not self.ssh_password:
            raise ValueError("ssh_password is required when passwordless_ssh is false")
        return self


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


# Jobs
class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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
    result_artifacts: list[dict] = Field(default_factory=list)

# Chat
class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=32_768)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=100)
    job_id: str | None = Field(default=None, pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    device_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_last_message(self):
        if self.messages[-1].role != "user":
            raise ValueError("the last chat message must have the user role")
        return self
