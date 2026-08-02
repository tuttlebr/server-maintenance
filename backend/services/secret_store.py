from cryptography.fernet import Fernet, InvalidToken

from backend.config import settings

PREFIX = "fernet:"


def _cipher() -> Fernet | None:
    key = settings.host_secret_key.strip()
    if not key:
        return None
    return Fernet(key.encode("utf-8"))


def encrypt_secret(value: str | None) -> str | None:
    if not value:
        return value
    cipher = _cipher()
    if cipher is None:
        raise RuntimeError("HOST_SECRET_KEY is required to encrypt stored host credentials")
    if value.startswith(PREFIX):
        return value
    token = cipher.encrypt(value.encode("utf-8")).decode("utf-8")
    return f"{PREFIX}{token}"


def decrypt_secret(value: str | None) -> str | None:
    if not value:
        return value
    if not value.startswith(PREFIX):
        raise RuntimeError("stored host credential is not encrypted")
    cipher = _cipher()
    if cipher is None:
        raise RuntimeError("HOST_SECRET_KEY is required to decrypt stored host credentials")
    try:
        return cipher.decrypt(value[len(PREFIX):].encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise RuntimeError("stored host credential could not be decrypted") from exc


def encrypt_existing_host_secrets() -> None:
    if _cipher() is None:
        return

    from backend.database import SessionLocal
    from backend.models import Host

    db = SessionLocal()
    try:
        changed = False
        for host in db.query(Host).all():
            encrypted_password = encrypt_secret(host.encrypted_ansible_password)
            encrypted_become = encrypt_secret(host.encrypted_ansible_become_password)
            if encrypted_password != host.encrypted_ansible_password:
                host.encrypted_ansible_password = encrypted_password
                changed = True
            if encrypted_become != host.encrypted_ansible_become_password:
                host.encrypted_ansible_become_password = encrypted_become
                changed = True
        if changed:
            db.commit()
    finally:
        db.close()
