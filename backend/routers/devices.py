from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.auth import get_current_user
from backend.capabilities import REACHY_APP_RESET, device_capabilities, normalize_capabilities
from backend.database import get_db
from backend.models import ContextDocument, Device, UserHostAssociation
from backend.schemas import (
    DeviceAnnotationsUpdate,
    DeviceCreate,
    DeviceEnrollmentRequest,
    DeviceResponse,
    DeviceSshEnrollmentRequest,
    DeviceUpdate,
    DiscoveryResponse,
)
from backend.services.ansible_runner import run_playbook
from backend.services.device_discovery import initial_profile, probe_reachy
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

router = APIRouter(prefix="/api/v2/devices", tags=["devices"])


def device_response(device: Device) -> DeviceResponse:
    endpoint = device.endpoint or device.ip_address or device.hostname
    transport = device.transport or "ssh"
    return DeviceResponse(
        id=device.id,
        name=device.name,
        inventory_name=device.hostname,
        endpoint=endpoint,
        transport=transport,
        ssh_user=device.ansible_user,
        passwordless_ssh=device.passwordless_ssh if device.ansible_user else True,
        daemon_port=(device.daemon_port or 8000) if transport == "reachy_daemon" else None,
        kind=device.kind or "generic",
        vendor=device.vendor,
        model=device.model,
        architecture=device.architecture,
        os_family=device.os_family,
        os_version=device.os_version,
        status=device.status or "unknown",
        capabilities=device_capabilities(device),
        facts=device.facts,
        annotations=device.annotations,
        memory_gb=device.memory_gb,
        gpu_model=device.gpu_model,
        driver_version=device.driver_version,
        cuda_version=device.cuda_version,
        nic_type=device.nic_type,
        nic_speed=device.nic_speed,
        disk_root_percent=device.disk_root_percent,
        disk_data_percent=device.disk_raid_percent,
        reboot_required=bool(device.reboot_required),
        last_seen=device.last_seen,
        discovered_at=device.discovered_at,
        created_at=device.created_at,
    )


def _verify_ssh_access(
    *,
    endpoint: str,
    ssh_user: str,
    passwordless_ssh: bool,
    ssh_password: str | None,
    bootstrap_password: str | None,
    fingerprint: str,
) -> None:
    try:
        trust_host_key(endpoint, fingerprint)
    except SshEnrollmentError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if passwordless_ssh:
        agent = get_agent_status()
        if not agent["ready"]:
            raise HTTPException(status_code=422, detail=agent["detail"])
        authenticated, detail = test_public_key_auth(endpoint, ssh_user)
        if not authenticated and bootstrap_password:
            installed, detail = install_agent_key(
                endpoint,
                ssh_user,
                bootstrap_password,
                agent["public_keys"][0],
            )
            if installed:
                authenticated, detail = test_public_key_auth(endpoint, ssh_user)
    else:
        authenticated, detail = test_password_auth(endpoint, ssh_user, ssh_password or "")
    if not authenticated:
        raise HTTPException(status_code=422, detail=detail)


@router.get("", response_model=list[DeviceResponse])
@router.get("/", response_model=list[DeviceResponse], include_in_schema=False)
def list_devices(db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    return [device_response(device) for device in db.query(Device).order_by(Device.hostname).all()]


@router.get("/{device_id}", response_model=DeviceResponse)
def get_device(device_id: int, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device_response(device)


@router.put("/{device_id}/annotations", response_model=DeviceResponse)
def update_device_annotations(
    device_id: int,
    payload: DeviceAnnotationsUpdate,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    device.annotations = payload.annotations
    db.commit()
    db.refresh(device)
    return device_response(device)


@router.post("/discover", response_model=DiscoveryResponse)
def discover_device(
    payload: DeviceCreate,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if db.query(Device).filter(Device.hostname == payload.name).first():
        raise HTTPException(status_code=409, detail=f"Device {payload.name} already exists")

    if payload.transport == "reachy_daemon":
        result = probe_reachy(payload.endpoint, payload.daemon_port or 8000)
        return DiscoveryResponse(
            reachable=result["reachable"],
            detail=result["detail"],
            kind=result["kind"],
            vendor=result["vendor"],
            model=result["model"],
            capabilities=result["capabilities"],
        )

    preview = preview_host_key(payload.name, payload.endpoint)
    profile = initial_profile("ssh")
    return DiscoveryResponse(
        reachable=preview["reachable"],
        trust_required=preview.get("trust_status") != "trusted",
        fingerprint=preview.get("fingerprint") or None,
        kind=profile["kind"],
        capabilities=profile["capabilities"],
        detail=preview.get("detail") or "SSH endpoint responded. Verify its ED25519 fingerprint before adding it.",
    )


@router.post("", response_model=DeviceResponse)
def add_device(
    payload: DeviceEnrollmentRequest,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    request = payload.device
    if db.query(Device).filter(Device.hostname == request.name).first():
        raise HTTPException(status_code=409, detail=f"Device {request.name} already exists")

    profile = initial_profile(request.transport)
    if request.transport == "reachy_daemon":
        result = probe_reachy(request.endpoint, request.daemon_port or 8000)
        if not result["reachable"]:
            raise HTTPException(status_code=422, detail=result["detail"])
        device = Device(
            hostname=request.name,
            display_name=request.name,
            endpoint=request.endpoint,
            ip_address=request.endpoint,
            transport="reachy_daemon",
            daemon_port=request.daemon_port or 8000,
            kind=profile["kind"],
            vendor=profile["vendor"],
            model=profile["model"],
            status="online",
            last_seen=datetime.now(timezone.utc),
            discovered_at=datetime.now(timezone.utc),
            machine_type="unknown",
        )
        device.capabilities = profile["capabilities"]
        device.facts = result.get("facts", {})
    else:
        if not payload.approval:
            raise HTTPException(status_code=422, detail="An approved SSH host fingerprint is required")
        _verify_ssh_access(
            endpoint=request.endpoint,
            ssh_user=request.ssh_user or "",
            passwordless_ssh=request.passwordless_ssh,
            ssh_password=request.ssh_password,
            bootstrap_password=request.bootstrap_password,
            fingerprint=payload.approval.fingerprint,
        )

        device = Device(
            hostname=request.name,
            display_name=request.name,
            endpoint=request.endpoint,
            ip_address=request.endpoint,
            transport="ssh",
            kind=profile["kind"],
            machine_type="unknown",
            ansible_user=request.ssh_user,
            encrypted_ansible_password=encrypt_secret(
                None if request.passwordless_ssh else request.ssh_password
            ),
            encrypted_ansible_become_password=encrypt_secret(request.become_password),
            status="unknown",
        )
        device.capabilities = profile["capabilities"]

    db.add(device)
    db.commit()
    db.refresh(device)
    regenerate_inventory(db)
    return device_response(device)


@router.post("/{device_id}/ssh-preview", response_model=DiscoveryResponse)
def preview_device_ssh(
    device_id: int,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    if device.transport != "reachy_daemon":
        raise HTTPException(status_code=400, detail="SSH maintenance setup is only needed for Reachy daemon devices")

    preview = preview_host_key(device.hostname, device.endpoint or device.hostname)
    return DiscoveryResponse(
        reachable=preview["reachable"],
        trust_required=preview.get("trust_status") != "trusted",
        fingerprint=preview.get("fingerprint") or None,
        kind=device.kind or "robot",
        vendor=device.vendor,
        model=device.model,
        capabilities=device_capabilities(device),
        detail=preview.get("detail") or "SSH endpoint responded. Verify its ED25519 fingerprint before enabling app reset.",
    )


@router.post("/{device_id}/ssh", response_model=DeviceResponse)
def configure_device_ssh(
    device_id: int,
    payload: DeviceSshEnrollmentRequest,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    if device.transport != "reachy_daemon":
        raise HTTPException(status_code=400, detail="SSH maintenance setup is only needed for Reachy daemon devices")

    endpoint = device.endpoint or device.hostname
    _verify_ssh_access(
        endpoint=endpoint,
        ssh_user=payload.ssh_user,
        passwordless_ssh=payload.passwordless_ssh,
        ssh_password=payload.ssh_password,
        bootstrap_password=payload.bootstrap_password,
        fingerprint=payload.approval.fingerprint,
    )
    device.ansible_user = payload.ssh_user
    device.encrypted_ansible_password = encrypt_secret(
        None if payload.passwordless_ssh else payload.ssh_password
    )
    device.encrypted_ansible_become_password = encrypt_secret(payload.become_password)
    device.capabilities = normalize_capabilities(
        [
            *initial_profile("reachy_daemon")["capabilities"],
            *device_capabilities(device),
            REACHY_APP_RESET,
        ]
    )
    db.commit()
    db.refresh(device)
    regenerate_inventory(db)
    return device_response(device)


@router.put("/{device_id}", response_model=DeviceResponse)
def update_device(
    device_id: int,
    payload: DeviceUpdate,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    if device.transport == "reachy_daemon" and any(
        value is not None
        for value in (
            payload.ssh_user,
            payload.ssh_password,
            payload.become_password,
            payload.passwordless_ssh,
        )
    ):
        raise HTTPException(
            status_code=400,
            detail="Use the verified Reachy SSH setup to change maintenance access",
        )
    if payload.display_name is not None:
        device.display_name = payload.display_name.strip()
    if payload.endpoint is not None:
        endpoint_changed = payload.endpoint != (device.endpoint or device.ip_address)
        device.endpoint = payload.endpoint
        device.ip_address = payload.endpoint
        if device.transport == "reachy_daemon" and endpoint_changed:
            device.ansible_user = None
            device.encrypted_ansible_password = None
            device.encrypted_ansible_become_password = None
            device.capabilities = [
                capability
                for capability in device_capabilities(device)
                if capability != REACHY_APP_RESET
            ]
    if payload.ssh_user is not None:
        device.ansible_user = payload.ssh_user
    if payload.passwordless_ssh is True:
        device.encrypted_ansible_password = None
    elif payload.ssh_password is not None:
        device.encrypted_ansible_password = encrypt_secret(payload.ssh_password)
    if payload.become_password is not None:
        device.encrypted_ansible_become_password = encrypt_secret(payload.become_password)
    if payload.daemon_port is not None:
        device.daemon_port = payload.daemon_port
    db.commit()
    db.refresh(device)
    regenerate_inventory(db)
    return device_response(device)


@router.delete("/{device_id}")
def delete_device(
    device_id: int,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    name = device.name
    db.query(UserHostAssociation).filter(UserHostAssociation.host_id == device.id).delete(
        synchronize_session=False
    )
    db.query(ContextDocument).filter(ContextDocument.device_id == device.id).update(
        {ContextDocument.device_id: None}, synchronize_session=False
    )
    db.delete(device)
    db.commit()
    regenerate_inventory(db)
    return {"detail": f"Removed {name} from Fleet Manager"}


@router.post("/{device_id}/scan")
async def scan_device(
    device_id: int,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    if device.transport == "reachy_daemon":
        result = probe_reachy(device.endpoint or device.hostname, device.daemon_port or 8000)
        device.status = "online" if result["reachable"] else "offline"
        if result["reachable"]:
            device.last_seen = datetime.now(timezone.utc)
            device.discovered_at = device.last_seen
            device.facts = result.get("facts", {})
        db.commit()
        return {"detail": result["detail"], "status": device.status}
    job_id = await run_playbook(db=db, playbook="host_facts.yml", hosts=[device.hostname], triggered_by=user)
    return {"job_id": job_id, "detail": f"Scanning {device.name}"}


@router.post("/scan-all")
async def scan_all_devices(db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    ssh_devices = db.query(Device).filter(Device.transport == "ssh").all()
    reachy_devices = db.query(Device).filter(Device.transport == "reachy_daemon").all()
    for device in reachy_devices:
        result = probe_reachy(device.endpoint or device.hostname, device.daemon_port or 8000)
        device.status = "online" if result["reachable"] else "offline"
        if result["reachable"]:
            device.last_seen = datetime.now(timezone.utc)
            device.facts = result.get("facts", {})
    db.commit()
    if not ssh_devices:
        return {"detail": f"Checked {len(reachy_devices)} Reachy device(s)"}
    job_id = await run_playbook(
        db=db,
        playbook="host_facts.yml",
        hosts=[device.hostname for device in ssh_devices],
        triggered_by=user,
    )
    return {"job_id": job_id, "detail": "Scanning all manageable devices"}
