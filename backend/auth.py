import hmac
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from backend.config import settings
from backend.services.tokens import TokenError, create_token, decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v2/auth/login")


def verify_admin(username: str, password: str) -> bool:
    return hmac.compare_digest(username, settings.admin_username) and hmac.compare_digest(
        password,
        settings.admin_password,
    )


def create_access_token(username: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expiry_hours)
    return create_token(username, expire, settings.secret_key)


def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token, settings.secret_key)
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        return username
    except TokenError:
        raise credentials_exception
