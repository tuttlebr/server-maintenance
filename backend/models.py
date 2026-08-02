from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, func

from backend.database import Base


class Host(Base):
    __tablename__ = "hosts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hostname = Column(String, unique=True, nullable=False, index=True)
    ip_address = Column(String)
    machine_type = Column(String)  # unknown | dgx_spark | dgx_workstation | cpu_node | gpu_node
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


class ManagedUser(Base):
    __tablename__ = "managed_users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, nullable=False, index=True)
    full_name = Column(String)
    email = Column(String)
    is_sudoer = Column(Boolean, default=False)
    groups = Column(String, default="users,docker")
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


class LoginThrottle(Base):
    __tablename__ = "login_throttles"

    key = Column(String(80), primary_key=True)
    window_started_at = Column(Integer, nullable=False)
    failure_count = Column(Integer, nullable=False, default=0)
    blocked_until = Column(Integer, nullable=False, default=0)
    updated_at = Column(Integer, nullable=False)
