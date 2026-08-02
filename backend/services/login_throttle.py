import hashlib
import hmac
import time

from backend.config import settings
from backend.database import SessionLocal
from backend.models import LoginThrottle

WINDOW_SECONDS = 10 * 60
ACCOUNT_MAX_FAILURES = 5
CLIENT_MAX_FAILURES = 20
BLOCK_SECONDS = 10 * 60
RETENTION_SECONDS = 24 * 60 * 60


def _digest(scope: str, value: str) -> str:
    digest = hmac.new(
        settings.secret_key.encode("utf-8"),
        f"{scope}:{value.casefold()}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{scope}:{digest}"


def _keys(client_address: str, username: str) -> tuple[tuple[str, int], tuple[str, int]]:
    return (
        (_digest("account", username), ACCOUNT_MAX_FAILURES),
        (_digest("client", client_address), CLIENT_MAX_FAILURES),
    )


def login_is_blocked(client_address: str, username: str, now: int | None = None) -> bool:
    current = int(time.time()) if now is None else now
    db = SessionLocal()
    try:
        for key, maximum in _keys(client_address, username):
            row = db.get(LoginThrottle, key)
            if not row:
                continue
            if row.blocked_until > current:
                return True
            if current - row.window_started_at < WINDOW_SECONDS and row.failure_count >= maximum:
                return True
        return False
    finally:
        db.close()


def record_login_failure(client_address: str, username: str, now: int | None = None) -> None:
    current = int(time.time()) if now is None else now
    db = SessionLocal()
    try:
        # Serialize the read-modify-write cycle across threads and processes so
        # parallel login attempts can't lose increments or race row creation.
        db.connection().exec_driver_sql("BEGIN IMMEDIATE")
        for key, maximum in _keys(client_address, username):
            row = db.get(LoginThrottle, key)
            if row is None:
                row = LoginThrottle(
                    key=key,
                    window_started_at=current,
                    failure_count=0,
                    blocked_until=0,
                    updated_at=current,
                )
                db.add(row)
            elif current - row.window_started_at >= WINDOW_SECONDS:
                row.window_started_at = current
                row.failure_count = 0
                row.blocked_until = 0

            row.failure_count += 1
            row.updated_at = current
            if row.failure_count >= maximum:
                row.blocked_until = current + BLOCK_SECONDS

        db.query(LoginThrottle).filter(
            LoginThrottle.updated_at < current - RETENTION_SECONDS
        ).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def clear_account_failures(username: str) -> None:
    db = SessionLocal()
    try:
        db.query(LoginThrottle).filter(
            LoginThrottle.key == _digest("account", username)
        ).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()
