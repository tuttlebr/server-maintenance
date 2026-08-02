from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from backend.auth import get_current_user
from backend.database import get_db
from backend.models import Host, ManagedUser, UserHostAssociation
from backend.schemas import (
    BulkPasswordResetRequest,
    BulkUserAdd,
    BulkUserUpdate,
    ChangePasswordRequest,
    RemoveUserRequest,
    SudoersRequest,
    UserResponse,
    _validate_linux_name,
)
from backend.services.ansible_runner import run_playbook
from backend.services.csv_parser import parse_csv

router = APIRouter(prefix="/api/v1/users", tags=["users"])


def _get_user_hosts(db: Session, user_id: int) -> list[str]:
    assocs = db.query(UserHostAssociation).filter(UserHostAssociation.user_id == user_id).all()
    host_ids = [a.host_id for a in assocs]
    if not host_ids:
        return []
    hosts = db.query(Host).filter(Host.id.in_(host_ids)).all()
    return [h.hostname for h in hosts]


def _user_to_response(db: Session, user: ManagedUser) -> dict:
    data = {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "email": user.email,
        "is_sudoer": user.is_sudoer,
        "groups": user.groups,
        "hosts": _get_user_hosts(db, user.id),
        "created_at": user.created_at,
    }
    return data


def _validated_username(username: str) -> str:
    try:
        return _validate_linux_name(username)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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

    job_id = await run_playbook(
        db=db,
        playbook="user_management.yml",
        hosts=payload.hosts,
        all_hosts=payload.all_hosts,
        extra_vars=extra_vars,
        triggered_by=user,
    )

    # Record users in DB
    for u in payload.users:
        username = u.username
        existing = db.query(ManagedUser).filter(ManagedUser.username == username).first()
        if not existing:
            managed = ManagedUser(
                username=username,
                full_name=u.full_name,
                email=u.email,
            )
            db.add(managed)
            db.commit()
            db.refresh(managed)
        else:
            managed = existing

        target_hosts = payload.hosts or [h.hostname for h in db.query(Host).all()]
        for host_name in target_hosts:
            host = db.query(Host).filter(Host.hostname == host_name).first()
            if host:
                assoc = (
                    db.query(UserHostAssociation)
                    .filter(
                        UserHostAssociation.user_id == managed.id,
                        UserHostAssociation.host_id == host.id,
                    )
                    .first()
                )
                if not assoc:
                    db.add(UserHostAssociation(user_id=managed.id, host_id=host.id))

    db.commit()
    return {"job_id": job_id, "detail": f"Adding {len(payload.users)} users"}


@router.post("/bulk-add-csv")
async def bulk_add_users_csv(
    file: UploadFile = File(...),
    hosts: str = "",
    password: str | None = None,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    content = (await file.read()).decode("utf-8")
    users = parse_csv(content)

    if not users:
        raise HTTPException(status_code=400, detail="No valid users found in CSV")

    host_list = [h.strip() for h in hosts.split(",") if h.strip()]
    if not host_list:
        raise HTTPException(status_code=400, detail="At least one target host is required for CSV provisioning")
    payload = BulkUserAdd(users=users, hosts=host_list, password=password)

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

    job_id = await run_playbook(
        db=db,
        playbook="user_management.yml",
        hosts=payload.hosts,
        all_hosts=payload.all_hosts,
        extra_vars=extra_vars,
        triggered_by=user,
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

    job_id = await run_playbook(
        db=db,
        playbook="change_password.yml",
        hosts=payload.hosts,
        all_hosts=payload.all_hosts,
        extra_vars=extra_vars,
        triggered_by=user,
    )
    return {"job_id": job_id, "detail": f"Changing password for {username}"}


@router.post("/bulk-password-reset")
async def bulk_password_reset(
    payload: BulkPasswordResetRequest,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if not payload.temp_password:
        raise HTTPException(status_code=400, detail="A temporary password is required for bulk resets")

    extra_vars: dict = {"interactive_mode": False}
    if payload.usernames:
        extra_vars["users_to_reset"] = payload.usernames
    extra_vars["temp_password"] = payload.temp_password

    job_id = await run_playbook(
        db=db,
        playbook="bulk_password_reset.yml",
        hosts=payload.hosts,
        all_hosts=payload.all_hosts,
        extra_vars=extra_vars,
        triggered_by=user,
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

    job_id = await run_playbook(
        db=db,
        playbook="manage_sudoers.yml",
        hosts=payload.hosts,
        all_hosts=payload.all_hosts,
        extra_vars=extra_vars,
        triggered_by=user,
    )

    managed = db.query(ManagedUser).filter(ManagedUser.username == username).first()
    if managed:
        managed.is_sudoer = True
        db.commit()

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

    job_id = await run_playbook(
        db=db,
        playbook="remove_sudoers.yml",
        hosts=payload.hosts,
        all_hosts=payload.all_hosts,
        extra_vars=extra_vars,
        triggered_by=user,
    )

    managed = db.query(ManagedUser).filter(ManagedUser.username == username).first()
    if managed:
        managed.is_sudoer = False
        db.commit()

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

    job_id = await run_playbook(
        db=db,
        playbook="remove_user.yml",
        hosts=payload.hosts,
        all_hosts=payload.all_hosts,
        extra_vars=extra_vars,
        triggered_by=user,
    )

    managed = db.query(ManagedUser).filter(ManagedUser.username == username).first()
    if managed:
        db.query(UserHostAssociation).filter(UserHostAssociation.user_id == managed.id).delete()
        db.delete(managed)
        db.commit()

    return {"job_id": job_id, "detail": f"Removing user {username}"}
