import asyncio
import csv
import io
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import ValidationError
from sqlalchemy.orm import Session

from backend.auth import get_current_user
from backend.database import get_db
from backend.models import Host
from backend.schemas import HostCreate, HostEnrollmentRequest, HostResponse, HostUpdate
from backend.services.ansible_runner import run_playbook
from backend.services.inventory_writer import regenerate_inventory
from backend.services.secret_store import encrypt_secret
from backend.services.ssh_enrollment import (
    SshEnrollmentError,
    get_agent_status,
    install_agent_key,
    preview_host_key,
    test_password_auth,
    test_public_key_auth,
    trust_host_key,
)

router = APIRouter(prefix="/api/v1/hosts", tags=["hosts"])

TRUE_VALUES = {"1", "true", "yes", "y", "on", "key", "keys", "ssh_key", "publickey", "public_key", "passwordless"}
FALSE_VALUES = {"0", "false", "no", "n", "off", "password", "ssh_password", "password_auth"}


def _parse_passwordless_ssh(value: str | None) -> bool | None:
    if value is None:
        return None
    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
    if not normalized:
        return None
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    return None


def _ssh_password(host: HostCreate) -> str | None:
    if host.passwordless_ssh:
        return None
    if not host.ansible_password:
        raise HTTPException(
            status_code=422,
            detail="An SSH password is required when passwordless SSH is disabled",
        )
    return host.ansible_password


def _new_db_host(host: HostCreate) -> Host:
    return Host(
        hostname=host.hostname,
        ip_address=host.ip_address,
        machine_type=host.machine_type,
        ansible_user=host.ansible_user,
        encrypted_ansible_password=encrypt_secret(_ssh_password(host)),
        encrypted_ansible_become_password=encrypt_secret(host.ansible_become_password),
        status="unknown",
    )


@router.get("/", response_model=list[HostResponse])
def list_hosts(db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    return db.query(Host).order_by(Host.hostname).all()


@router.post("/", response_model=HostResponse)
def add_host(
    host: HostCreate,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    existing = db.query(Host).filter(Host.hostname == host.hostname).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Host {host.hostname} already exists")

    db_host = _new_db_host(host)
    db.add(db_host)
    db.commit()
    db.refresh(db_host)

    regenerate_inventory(db)
    return db_host


@router.post("/bulk-add")
async def bulk_add_hosts(
    payload: list[HostCreate],
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    added = []
    skipped = []
    for host in payload:
        existing = db.query(Host).filter(Host.hostname == host.hostname).first()
        if existing:
            skipped.append(host.hostname)
            continue
        db_host = _new_db_host(host)
        db.add(db_host)
        added.append(host.hostname)

    if added:
        db.commit()
        regenerate_inventory(db)

    return {
        "added": added,
        "skipped": skipped,
        "detail": f"Added {len(added)} hosts, skipped {len(skipped)} (already exist)",
    }


@router.post("/bulk-add-csv")
async def bulk_add_hosts_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    """Bulk add hosts from CSV, including an optional one-time bootstrap password."""
    content = (await file.read()).decode("utf-8")
    reader = csv.reader(io.StringIO(content))
    rows = list(reader)

    if not rows:
        raise HTTPException(status_code=400, detail="Empty CSV file")

    # Detect header
    first_row = [c.strip().lower() for c in rows[0]]
    has_header = "hostname" in first_row or "host" in first_row
    if has_header:
        header = first_row
        data_rows = rows[1:]
    else:
        header = [
            "hostname",
            "ip_address",
            "machine_type",
            "ansible_user",
            "ansible_password",
            "ansible_become_password",
            "passwordless_ssh",
            "bootstrap_password",
        ]
        data_rows = rows

    # Map column indices
    col_map = {}
    aliases = {
        "hostname": ["hostname", "host", "name"],
        "ip_address": ["ip_address", "ip", "address", "ansible_host"],
        "machine_type": ["machine_type", "type"],
        "ansible_user": ["ansible_user", "ssh_user", "user", "username"],
        "ansible_password": ["ansible_password", "ssh_password", "password", "ssh_pass"],
        "ansible_become_password": ["ansible_become_password", "sudo_password", "become_password", "become_pass"],
        "bootstrap_password": ["bootstrap_password", "one_time_password", "enrollment_password"],
        "passwordless_ssh": [
            "passwordless_ssh",
            "ssh_passwordless",
            "passwordless",
            "key_based_auth",
            "key_auth",
            "ssh_key",
            "ssh_auth_method",
            "auth_method",
        ],
    }
    for field, names in aliases.items():
        for i, col in enumerate(header):
            if col in names:
                col_map[field] = i
                break

    if "hostname" not in col_map:
        col_map["hostname"] = 0

    hosts_to_add = []
    for row in data_rows:
        if not row or all(c.strip() == "" for c in row):
            continue
        def get_col(field):
            idx = col_map.get(field)
            if idx is not None and idx < len(row):
                return row[idx].strip()
            return None

        hostname = get_col("hostname")
        if not hostname:
            continue
        passwordless_value = get_col("passwordless_ssh")
        passwordless_ssh = _parse_passwordless_ssh(passwordless_value)
        if passwordless_value and passwordless_ssh is None:
            continue
        ssh_password = get_col("ansible_password")
        if passwordless_ssh is None:
            passwordless_ssh = not bool(ssh_password)
        if passwordless_ssh is False and not ssh_password:
            continue

        try:
            hosts_to_add.append(HostCreate(
                hostname=hostname,
                ip_address=get_col("ip_address"),
                machine_type=get_col("machine_type") or "unknown",
                ansible_user=get_col("ansible_user"),
                ansible_password=ssh_password,
                ansible_become_password=get_col("ansible_become_password"),
                bootstrap_password=get_col("bootstrap_password"),
                passwordless_ssh=passwordless_ssh,
            ))
        except ValidationError:
            continue

    if not hosts_to_add:
        raise HTTPException(status_code=400, detail="No valid hosts found in CSV")

    return await bulk_add_hosts(hosts_to_add, db=db, user=user)


@router.post("/enrollment-preview")
async def enrollment_preview(
    payload: list[HostCreate],
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if not payload:
        raise HTTPException(status_code=422, detail="At least one host is required")
    if len(payload) > 200:
        raise HTTPException(status_code=422, detail="At most 200 hosts can be enrolled at once")
    hostnames = [host.hostname for host in payload]
    if len(hostnames) != len(set(hostnames)):
        raise HTTPException(status_code=422, detail="Hostnames must be unique")

    existing = {
        row.hostname
        for row in db.query(Host.hostname).filter(Host.hostname.in_(hostnames)).all()
    }
    agent, *previews = await asyncio.gather(
        asyncio.to_thread(get_agent_status),
        *[
            asyncio.to_thread(
                preview_host_key,
                host.hostname,
                host.ip_address or host.hostname,
            )
            for host in payload
        ],
    )
    for host, preview in zip(payload, previews):
        preview["passwordless_ssh"] = host.passwordless_ssh
        preview["bootstrap_available"] = bool(host.bootstrap_password)
        preview["already_exists"] = host.hostname in existing

    return {
        "agent": agent,
        "hosts": previews,
        "ready": all(preview["reachable"] for preview in previews)
        and (
            agent["ready"]
            or all(not host.passwordless_ssh for host in payload)
        ),
    }


@router.post("/bulk-enroll")
async def bulk_enroll_hosts(
    payload: HostEnrollmentRequest,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    approvals = {
        approval.hostname: approval.fingerprint
        for approval in payload.approvals
    }
    existing = {
        row.hostname
        for row in db.query(Host.hostname)
        .filter(Host.hostname.in_([host.hostname for host in payload.hosts]))
        .all()
    }
    candidates = [host for host in payload.hosts if host.hostname not in existing]
    agent = await asyncio.to_thread(get_agent_status)
    if any(host.passwordless_ssh for host in candidates) and not agent["ready"]:
        raise HTTPException(status_code=422, detail=agent["detail"])

    async def enroll_one(host: HostCreate) -> dict:
        address = host.ip_address or host.hostname
        try:
            await asyncio.to_thread(
                trust_host_key,
                address,
                approvals[host.hostname],
            )
        except SshEnrollmentError as exc:
            return {
                "hostname": host.hostname,
                "status": "failed",
                "detail": str(exc),
            }

        if host.passwordless_ssh:
            authenticated, detail = await asyncio.to_thread(
                test_public_key_auth,
                address,
                host.ansible_user,
            )
            if not authenticated and host.bootstrap_password:
                installed, install_detail = await asyncio.to_thread(
                    install_agent_key,
                    address,
                    host.ansible_user,
                    host.bootstrap_password,
                    agent["public_keys"][0],
                )
                if not installed:
                    return {
                        "hostname": host.hostname,
                        "status": "failed",
                        "detail": f"Fleet key installation failed: {install_detail}",
                    }
                authenticated, detail = await asyncio.to_thread(
                    test_public_key_auth,
                    address,
                    host.ansible_user,
                )
            if not authenticated:
                return {
                    "hostname": host.hostname,
                    "status": "failed",
                    "detail": (
                        f"Fleet key authentication failed for {host.ansible_user}@{address}: "
                        f"{detail}. Install the dedicated fleet agent key for that remote user "
                        "or provide a one-time bootstrap password."
                    ),
                }
        else:
            authenticated, detail = await asyncio.to_thread(
                test_password_auth,
                address,
                host.ansible_user,
                host.ansible_password,
            )
            if not authenticated:
                return {
                    "hostname": host.hostname,
                    "status": "failed",
                    "detail": (
                        f"Password authentication failed for {host.ansible_user}@{address}: "
                        f"{detail}"
                    ),
                }

        return {
            "hostname": host.hostname,
            "status": "ready",
            "detail": detail,
        }

    results = await asyncio.gather(*[enroll_one(host) for host in candidates])
    ready = {result["hostname"] for result in results if result["status"] == "ready"}
    added = []
    for host in candidates:
        if host.hostname not in ready:
            continue
        db.add(_new_db_host(host))
        added.append(host.hostname)
    if added:
        db.commit()
        regenerate_inventory(db)

    failed = [result for result in results if result["status"] == "failed"]
    skipped = sorted(existing)
    return {
        "added": added,
        "skipped": skipped,
        "failed": failed,
        "results": results,
        "detail": (
            f"Enrolled {len(added)} host(s); "
            f"{len(failed)} failed; {len(skipped)} already existed"
        ),
    }


@router.get("/{hostname}", response_model=HostResponse)
def get_host(
    hostname: str,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    host = db.query(Host).filter(Host.hostname == hostname).first()
    if not host:
        raise HTTPException(status_code=404, detail=f"Host {hostname} not found")
    return host


@router.put("/{hostname}", response_model=HostResponse)
def update_host(
    hostname: str,
    update: HostUpdate,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    host = db.query(Host).filter(Host.hostname == hostname).first()
    if not host:
        raise HTTPException(status_code=404, detail=f"Host {hostname} not found")

    if update.ip_address is not None:
        host.ip_address = update.ip_address
    if update.machine_type is not None:
        host.machine_type = update.machine_type
    if update.ansible_user is not None:
        host.ansible_user = update.ansible_user
    if update.passwordless_ssh is True:
        host.encrypted_ansible_password = None
    elif update.passwordless_ssh is False and host.passwordless_ssh and not update.ansible_password:
        raise HTTPException(
            status_code=422,
            detail="An SSH password is required when switching from key authentication",
        )
    elif update.ansible_password is not None:
        host.encrypted_ansible_password = encrypt_secret(update.ansible_password)
    if update.ansible_become_password is not None:
        host.encrypted_ansible_become_password = encrypt_secret(update.ansible_become_password)

    db.commit()
    db.refresh(host)
    regenerate_inventory(db)
    return host


@router.delete("/{hostname}")
def delete_host(
    hostname: str,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    host = db.query(Host).filter(Host.hostname == hostname).first()
    if not host:
        raise HTTPException(status_code=404, detail=f"Host {hostname} not found")

    db.delete(host)
    db.commit()
    regenerate_inventory(db)
    return {"detail": f"Host {hostname} removed"}


@router.post("/{hostname}/scan")
async def scan_host(
    hostname: str,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    host = db.query(Host).filter(Host.hostname == hostname).first()
    if not host:
        raise HTTPException(status_code=404, detail=f"Host {hostname} not found")

    job_id = await run_playbook(
        db=db,
        playbook="host_facts.yml",
        hosts=[hostname],
        all_hosts=False,
        triggered_by=user,
    )
    return {"job_id": job_id, "detail": f"Scanning {hostname}"}


@router.post("/scan-all")
async def scan_all_hosts(
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    job_id = await run_playbook(
        db=db,
        playbook="host_facts.yml",
        all_hosts=True,
        triggered_by=user,
    )
    return {"job_id": job_id, "detail": "Scanning all hosts"}
