import json

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, func

from backend.database import Base


class Device(Base):
    __tablename__ = "hosts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hostname = Column(String, unique=True, nullable=False, index=True)
    ip_address = Column(String)
    # Legacy deployment classification. It is retained only so the migration can
    # enrich existing rows and older playbooks can finish moving to capabilities.
    machine_type = Column(String)
    display_name = Column(String)
    kind = Column(String, default="generic")  # server | workstation | edge | robot | generic
    vendor = Column(String)
    model = Column(String)
    architecture = Column(String)
    os_family = Column(String)
    transport = Column(String, default="ssh")  # ssh | reachy_daemon
    endpoint = Column(String)
    daemon_port = Column(Integer)
    capabilities_json = Column(Text, default="[]")
    facts_json = Column(Text, default="{}")
    annotations_json = Column(Text, default="{}")
    discovered_at = Column(DateTime)
    ansible_user = Column(String)
    # Keep the deployed column names while making the ciphertext-only storage
    # contract explicit in the ORM. Plaintext credentials never belong here.
    encrypted_ansible_password = Column("ansible_password", String)
    encrypted_ansible_become_password = Column("ansible_become_password", String)
    os_version = Column(String)
    gpu_model = Column(String)
    driver_version = Column(String)
    cuda_version = Column(String)
    memory_gb = Column(Integer)
    nic_type = Column(String)
    nic_speed = Column(String)
    fabric_manager_status = Column(String)
    disk_root_percent = Column(Integer)
    disk_raid_percent = Column(Integer)
    status = Column(String, default="unknown")  # online | offline | unknown
    reboot_required = Column(Boolean, default=False)
    last_seen = Column(DateTime)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    @property
    def passwordless_ssh(self) -> bool:
        return not bool(self.encrypted_ansible_password)

    @property
    def capabilities(self) -> list[str]:
        try:
            value = json.loads(self.capabilities_json or "[]")
            return sorted({str(item) for item in value if item}) if isinstance(value, list) else []
        except (TypeError, ValueError):
            return []

    @capabilities.setter
    def capabilities(self, value: list[str]) -> None:
        self.capabilities_json = json.dumps(sorted(set(value or [])))

    @property
    def facts(self) -> dict:
        try:
            value = json.loads(self.facts_json or "{}")
            return value if isinstance(value, dict) else {}
        except (TypeError, ValueError):
            return {}

    @facts.setter
    def facts(self, value: dict) -> None:
        self.facts_json = json.dumps(value or {}, sort_keys=True)

    @property
    def annotations(self) -> dict[str, str]:
        try:
            value = json.loads(self.annotations_json or "{}")
            if not isinstance(value, dict):
                return {}
            return {str(key): str(item) for key, item in value.items() if key and item is not None}
        except (TypeError, ValueError):
            return {}

    @annotations.setter
    def annotations(self, value: dict[str, str]) -> None:
        self.annotations_json = json.dumps(value or {}, sort_keys=True)

    @property
    def name(self) -> str:
        return self.display_name or self.hostname


# Internal compatibility alias while the Ansible-oriented services are renamed
# incrementally. Public API contracts expose Device only.
Host = Device


class ManagedUser(Base):
    __tablename__ = "managed_users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, nullable=False, index=True)
    full_name = Column(String)
    email = Column(String)
    is_sudoer = Column(Boolean, default=False)
    groups = Column(String, default="users")
    created_at = Column(DateTime, default=func.now())


class UserHostAssociation(Base):
    __tablename__ = "user_host_assoc"

    user_id = Column(Integer, ForeignKey("managed_users.id", ondelete="CASCADE"), primary_key=True)
    host_id = Column(Integer, ForeignKey("hosts.id", ondelete="CASCADE"), primary_key=True)
    provisioned_at = Column(DateTime, default=func.now())


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String, unique=True, nullable=False, index=True)
    playbook = Column(String, nullable=False)
    target_hosts = Column(String)
    status = Column(String, default="pending")  # pending | running | success | failed | cancelled
    started_at = Column(DateTime)
    finished_at = Column(DateTime)
    duration_seconds = Column(Integer)
    triggered_by = Column(String, default="admin")
    extra_vars = Column(Text)  # JSON string, passwords redacted
    output_log = Column(Text)
    error_summary = Column(Text)
    recap = Column(Text)  # PLAY RECAP summary
    created_at = Column(DateTime, default=func.now())

    @property
    def target_devices(self) -> str | None:
        return self.target_hosts


class ContextDocument(Base):
    __tablename__ = "context_documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), nullable=False)
    original_filename = Column(String(255), nullable=False)
    content_type = Column(String(80), nullable=False)
    content = Column(Text, nullable=False)
    size_bytes = Column(Integer, nullable=False)
    sha256 = Column(String(64), nullable=False, index=True)
    device_id = Column(Integer, ForeignKey("hosts.id", ondelete="SET NULL"), nullable=True, index=True)
    uploaded_by = Column(String(128), nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)


class LoginThrottle(Base):
    __tablename__ = "login_throttles"

    key = Column(String(80), primary_key=True)
    window_started_at = Column(Integer, nullable=False)
    failure_count = Column(Integer, nullable=False, default=0)
    blocked_until = Column(Integer, nullable=False, default=0)
    updated_at = Column(Integer, nullable=False)
