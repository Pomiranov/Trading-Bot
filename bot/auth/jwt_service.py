"""JWT access tokens — RS256 with persistent key pair."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import jwt

from config import config

logger = logging.getLogger(__name__)

_KEY_DIR = Path(__file__).parent.parent / "data" / "jwt"
_PRIVATE_KEY_FILE = _KEY_DIR / "private.pem"
_PUBLIC_KEY_FILE = _KEY_DIR / "public.pem"

_private_key: str | None = None
_public_key: str | None = None


class JWTError(Exception):
    pass


def _ensure_keys() -> tuple[str, str]:
    global _private_key, _public_key
    if _private_key and _public_key:
        return _private_key, _public_key

    env_private = config.auth.jwt_private_key_pem.strip()
    env_public = config.auth.jwt_public_key_pem.strip()
    if env_private and env_public:
        _private_key, _public_key = env_private, env_public
        return _private_key, _public_key

    if _PRIVATE_KEY_FILE.exists() and _PUBLIC_KEY_FILE.exists():
        _private_key = _PRIVATE_KEY_FILE.read_text(encoding="utf-8")
        _public_key = _PUBLIC_KEY_FILE.read_text(encoding="utf-8")
        return _private_key, _public_key

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public_pem = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")

    _KEY_DIR.mkdir(parents=True, exist_ok=True)
    _PRIVATE_KEY_FILE.write_text(private_pem, encoding="utf-8")
    _PUBLIC_KEY_FILE.write_text(public_pem, encoding="utf-8")
    try:
        _PRIVATE_KEY_FILE.chmod(0o600)
    except OSError:
        pass

    logger.info("Generated new JWT RSA key pair at %s", _KEY_DIR)
    _private_key, _public_key = private_pem, public_pem
    return _private_key, _public_key


def create_access_token(
    *,
    user_id: int,
    username: str,
    role: str,
    session_id: str,
) -> tuple[str, str, datetime]:
    private_key, _ = _ensure_keys()
    jti = uuid.uuid4().hex
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=config.auth.access_token_ttl_minutes)
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "sid": session_id,
        "jti": jti,
        "iss": config.auth.jwt_issuer,
        "aud": config.auth.jwt_audience,
        "iat": int(now.timestamp()),
        "exp": int(expires.timestamp()),
    }
    token = jwt.encode(payload, private_key, algorithm="RS256")
    return token, jti, expires


def decode_access_token(token: str) -> dict[str, Any]:
    _, public_key = _ensure_keys()
    try:
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=config.auth.jwt_audience,
            issuer=config.auth.jwt_issuer,
        )
    except jwt.PyJWTError as exc:
        raise JWTError(str(exc)) from exc
    return payload