from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from backend.auth import get_current_user
from backend.database import get_db
from backend.models import Host, ManagedUser, UserHostAssociation
from backend.capabilities import USERS_MANAGE, has_capability, facts_are_stale
from backend.schemas import (
    BulkPasswordResetRequest,
    BulkUserAdd,
    BulkUserUpdate,
    ChangePasswordRequest,
    RemoveUserRequest,
    SudoersRequest,
    _validate_linux_name,
)
from backend.services.ansible_runner import run_playbook
from backend.services.csv_parser import parse_csv

router = APIRouter(prefix="/api/v2/users", tags=["access"])


def _get_user_devices(db: Session, user_id: int) -> list[int]:
    assocs = db.query(UserHostAssociation).filter(UserHostAssociation.user_id == user_id).all()
    host_ids = [a.host_id for a in assocs]
    if not host_ids:
        return []
    return sorted(host_ids)


def _user_to_response(db: Session, user: ManagedUser) -> dict:
    data = {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "email": user.email,
        "placements": [{"device_id": a.host_id, "groups": a.groups, "shell": a.shell, "managed_sudo": a.managed_sudo, "sudo_policy": a.sudo_policy, "observed_at": a.observed_at, "state": a.state} for a in db.query(UserHostAssociation).filter_by(user_id=user.id).all()],
        "device_ids": _get_user_devices(db, user.id),
        "created_at": user.created_at,
    }
    return data


def _validated_username(username: str) -> str:
    try:
        return _validate_linux_name(username)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _target_devices(payload, db: Session, *, inspect=False) -> list[Host]:
    if payload.all_devices or not payload.device_ids:
        raise HTTPException(status_code=400, detail="Select explicit target devices. Fleet-wide implicit account changes are disabled.")
    query = db.query(Host).filter((Host.transport == "ssh") | (Host.transport.is_(None)))
    devices = query.order_by(Host.hostname).all() if payload.all_devices else query.filter(
        Host.id.in_(payload.device_ids or [])
    ).order_by(Host.hostname).all()
    if not payload.all_devices and len(devices) != len(payload.device_ids or []):
        found = {device.id for device in devices}
        missing = [str(device_id) for device_id in payload.device_ids or [] if device_id not in found]
        raise HTTPException(status_code=404, detail=f"Unknown or non-SSH device IDs: {', '.join(missing)}")
    unsupported = [device.name for device in devices if not has_capability(device, USERS_MANAGE)]
    if unsupported:
        raise HTTPException(status_code=400, detail=f"Linux account management is not supported on: {', '.join(unsupported)}")
    if not devices:
        raise HTTPException(status_code=400, detail="No access-capable devices are available")
    if not inspect:
        for device in devices:
            if device.os_family not in {"Debian", "RedHat"}:
                raise HTTPException(status_code=409, detail=f"Account changes support discovered Debian and Red Hat family devices: {device.name}")
            if device.recovery_required:
                raise HTTPException(status_code=409, detail=f"{device.name} requires recovery verification")
            if facts_are_stale(device):
                raise HTTPException(status_code=409, detail=f"Scan {device.name} before changing accounts")
    return devices


@router.get("/")
def list_users(db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    users = db.query(ManagedUser).order_by(ManagedUser.username).all()
    return [_user_to_response(db, u) for u in users]


@router.post("/bulk-add")
async def bulk_add_users(
    payload: BulkUserAdd,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    extra_vars = {
        "user_records": [
            {"username": u.username, "full_name": u.full_name, "email": u.email}
            for u in payload.users
        ],
        "interactive_mode": False,
    }
    if payload.password:
        extra_vars["default_password"] = payload.password

    target_devices = _target_devices(payload, db)
    if any(device.os_family not in {"Debian", "RedHat"} for device in target_devices):
        raise HTTPException(status_code=400, detail="Provisioning supports discovered Debian and Red Hat family devices")
    target_names = [device.hostname for device in target_devices]
    job_id = await run_playbook(
        db=db,
        playbook="user_management.yml",
        hosts=target_names,
        all_hosts=False,
        extra_vars=extra_vars,
        triggered_by=user,
        request_key=payload.request_key,
        completion_action={
            "type": "provision_users",
            "hostnames": target_names,
            "users": extra_vars["user_records"],
        },
    )
    return {"job_id": job_id, "detail": f"Adding {len(payload.users)} users"}


@router.post("/bulk-add-csv")
async def bulk_add_users_csv(
    file: UploadFile = File(...),
    device_ids: str = "",
    password: str | None = None,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    content = (await file.read()).decode("utf-8")
    users = parse_csv(content)

    if not users:
        raise HTTPException(status_code=400, detail="No valid users found in CSV")

    try:
        target_ids = [int(value.strip()) for value in device_ids.split(",") if value.strip()]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="device_ids must be comma-separated integers") from exc
    if not target_ids:
        raise HTTPException(status_code=400, detail="At least one target device is required for CSV provisioning")
    payload = BulkUserAdd(users=users, device_ids=target_ids, password=password)

    return await bulk_add_users(payload, db=db, user=user)


@router.put("/bulk-update")
async def bulk_update_users(
    payload: BulkUserUpdate,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    extra_vars: dict = {
        "target_usernames": payload.usernames,
        "interactive_mode": False,
    }
    if payload.groups:
        extra_vars["user_groups"] = payload.groups
    if payload.shell:
        extra_vars["user_shell"] = payload.shell

    target_devices = _target_devices(payload, db)
    job_id = await run_playbook(
        db=db,
        playbook="user_management.yml",
        hosts=[device.hostname for device in target_devices],
        all_hosts=False,
        extra_vars=extra_vars,
        triggered_by=user,
        request_key=payload.request_key,
        completion_action={
            "type": "update_users",
            "hostnames": [device.hostname for device in target_devices],
            "usernames": payload.usernames,
            "groups": payload.groups,
        },
    )
    return {"job_id": job_id, "detail": f"Updating {len(payload.usernames)} users"}


@router.post("/{username}/change-password")
async def change_password(
    username: str,
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    username = _validated_username(username)
    extra_vars = {
        "target_username": username,
        "new_password": payload.new_password,
        "force_change": "yes" if payload.force_change else "no",
        "interactive_mode": False,
    }

    target_devices = _target_devices(payload, db)
    job_id = await run_playbook(
        db=db,
        playbook="change_password.yml",
        hosts=[device.hostname for device in target_devices],
        all_hosts=False,
        extra_vars=extra_vars,
        triggered_by=user,
        request_key=payload.request_key,
    )
    return {"job_id": job_id, "detail": f"Changing password for {username}"}


@router.post("/bulk-password-reset")
async def bulk_password_reset(
    payload: BulkPasswordResetRequest,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if not payload.usernames:
        raise HTTPException(status_code=400, detail="Select explicit account names for a password reset")
    if not payload.temp_password:
        raise HTTPException(status_code=400, detail="A temporary password is required for bulk resets")

    extra_vars: dict = {"interactive_mode": False}
    if payload.usernames:
        extra_vars["users_to_reset"] = payload.usernames
    extra_vars["temp_password"] = payload.temp_password

    target_devices = _target_devices(payload, db)
    job_id = await run_playbook(
        db=db,
        playbook="bulk_password_reset.yml",
        hosts=[device.hostname for device in target_devices],
        all_hosts=False,
        extra_vars=extra_vars,
        triggered_by=user,
        request_key=payload.request_key,
    )
    return {"job_id": job_id, "detail": "Bulk password reset initiated"}


@router.post("/{username}/add-sudoers")
async def add_sudoers(
    username: str,
    payload: SudoersRequest,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    username = _validated_username(username)
    extra_vars = {"root_users": [username]}

    target_devices = _target_devices(payload, db)
    job_id = await run_playbook(
        db=db,
        playbook="manage_sudoers.yml",
        hosts=[device.hostname for device in target_devices],
        all_hosts=False,
        extra_vars=extra_vars,
        triggered_by=user,
        request_key=payload.request_key,
        completion_action={
            "type": "set_sudoer",
            "hostnames": [device.hostname for device in target_devices],
            "username": username,
            "enabled": True,
        },
    )

    return {"job_id": job_id, "detail": f"Adding {username} to sudoers"}


@router.post("/{username}/remove-sudoers")
async def remove_sudoers(
    username: str,
    payload: SudoersRequest,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    username = _validated_username(username)
    extra_vars = {"target_username": username}

    target_devices = _target_devices(payload, db)
    job_id = await run_playbook(
        db=db,
        playbook="remove_sudoers.yml",
        hosts=[device.hostname for device in target_devices],
        all_hosts=False,
        extra_vars=extra_vars,
        triggered_by=user,
        request_key=payload.request_key,
        completion_action={
            "type": "set_sudoer",
            "hostnames": [device.hostname for device in target_devices],
            "username": username,
            "enabled": False,
        },
    )

    return {"job_id": job_id, "detail": f"Removing {username} from sudoers"}


@router.delete("/{username}")
async def remove_user(
    username: str,
    payload: RemoveUserRequest,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    username = _validated_username(username)
    extra_vars = {
        "target_username": username,
        "remove_home": payload.remove_home,
    }

    target_devices = _target_devices(payload, db)
    job_id = await run_playbook(
        db=db,
        playbook="remove_user.yml",
        hosts=[device.hostname for device in target_devices],
        all_hosts=False,
        extra_vars=extra_vars,
        triggered_by=user,
        request_key=payload.request_key,
        completion_action={
            "type": "remove_user",
            "hostnames": [device.hostname for device in target_devices],
            "username": username,
        },
    )

    return {"job_id": job_id, "detail": f"Removing user {username}"}


@router.post("/inspect")
async def inspect_accounts(payload: SudoersRequest, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    devices = _target_devices(payload, db, inspect=True)
    job_id = await run_playbook(db, "access_inspect.yml", hosts=[d.hostname for d in devices], triggered_by=user, request_key=payload.request_key)
    return {"job_id": job_id, "detail": "Account inspection queued"}
