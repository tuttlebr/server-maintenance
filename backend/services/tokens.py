import base64
import hashlib
import hmac
import json
import time
from datetime import datetime, timezone


class TokenError(ValueError):
    pass


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64decode(raw: str) -> bytes:
    padding = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode((raw + padding).encode("ascii"))


def _json_b64(data: dict) -> str:
    encoded = json.dumps(data, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return _b64encode(encoded)


def _sign(message: str, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), message.encode("ascii"), hashlib.sha256).digest()
    return _b64encode(digest)


def create_token(subject: str, expires_at: datetime, secret: str) -> str:
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    header = _json_b64({"alg": "HS256", "typ": "JWT"})
    payload = _json_b64({"sub": subject, "exp": int(expires_at.timestamp())})
    signing_input = f"{header}.{payload}"
    return f"{signing_input}.{_sign(signing_input, secret)}"


def decode_token(token: str, secret: str) -> dict:
    try:
        header_b64, payload_b64, signature = token.split(".", 2)
    except ValueError as exc:
        raise TokenError("Invalid token format") from exc

    signing_input = f"{header_b64}.{payload_b64}"
    expected = _sign(signing_input, secret)
    if not hmac.compare_digest(signature, expected):
        raise TokenError("Invalid token signature")

    try:
        header = json.loads(_b64decode(header_b64))
        payload = json.loads(_b64decode(payload_b64))
    except (ValueError, json.JSONDecodeError) as exc:
        raise TokenError("Invalid token payload") from exc

    if header.get("alg") != "HS256":
        raise TokenError("Unsupported token algorithm")

    exp = payload.get("exp")
    if not isinstance(exp, int) or exp < int(time.time()):
        raise TokenError("Token has expired")
    return payload
