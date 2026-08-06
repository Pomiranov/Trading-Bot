"""Password hashing for dashboard operators.

Argon2id when ``argon2-cffi`` is installed, scrypt (via Werkzeug, which ships
with Flask) otherwise. The algorithm is encoded in the digest, so a database
written by one is readable by the other and upgrading is a re-hash on next login
rather than a migration.

Non-negotiables:

* No default password anywhere, in code or in configuration.
* No plaintext or reversible form is ever stored, logged or returned.
* Verification is constant-time with respect to the digest, and the *absence* of
  a user costs the same as a wrong password (see ``dummy_verify``), so login
  timing does not enumerate accounts.
"""

from __future__ import annotations

import hmac
import logging
import os
import secrets
from typing import Optional

logger = logging.getLogger(__name__)

MIN_PASSWORD_LENGTH = 12

try:  # pragma: no cover - depends on the deployment's installed packages
    from argon2 import PasswordHasher
    from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

    # OWASP-recommended baseline for interactive login: 64 MiB, 3 passes.
    _hasher = PasswordHasher(time_cost=3, memory_cost=64 * 1024, parallelism=4)
    ARGON2_AVAILABLE = True
except Exception:  # noqa: BLE001
    _hasher = None
    ARGON2_AVAILABLE = False

from werkzeug.security import check_password_hash, generate_password_hash

#: Digest used by `dummy_verify` to spend comparable work when no user exists.
#: Generated once per process from a random secret, so it is never a real hash.
_DUMMY_DIGEST: Optional[str] = None


def algorithm() -> str:
    return "argon2id" if ARGON2_AVAILABLE else "scrypt"


def hash_password(password: str) -> str:
    if not password or len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"password must be at least {MIN_PASSWORD_LENGTH} characters")
    if ARGON2_AVAILABLE and _hasher is not None:
        return _hasher.hash(password)
    # Werkzeug's scrypt digest is self-describing: "scrypt:32768:8:1$salt$hash".
    return generate_password_hash(password, method="scrypt")


def verify_password(digest: str, password: str) -> bool:
    """Constant-time-ish verification. Never raises for a malformed digest."""
    if not digest or not password:
        return False
    try:
        if digest.startswith("$argon2"):
            if not (ARGON2_AVAILABLE and _hasher is not None):
                logger.error(
                    "Хеш пароля создан argon2, но argon2-cffi не установлен — "
                    "вход невозможен. Установите argon2-cffi или пересоздайте пользователя."
                )
                return False
            try:
                _hasher.verify(digest, password)
                return True
            except (VerifyMismatchError, VerificationError, InvalidHashError):
                return False
        return check_password_hash(digest, password)
    except Exception:  # noqa: BLE001 — a broken digest is a failed login, not a 500
        logger.warning("Не удалось проверить хеш пароля (некорректный формат)")
        return False


def needs_rehash(digest: str) -> bool:
    """Whether the stored digest should be upgraded on the next successful login."""
    if not digest:
        return True
    if ARGON2_AVAILABLE and _hasher is not None:
        if not digest.startswith("$argon2"):
            return True
        try:
            return bool(_hasher.check_needs_rehash(digest))
        except Exception:  # noqa: BLE001
            return True
    return digest.startswith("$argon2")


def dummy_verify(password: str) -> None:
    """Burn comparable time when the username does not exist.

    Without this, a missing user returns immediately and a present one costs a
    KDF, which is a reliable account-enumeration oracle even though both paths
    return the same generic error message.
    """
    global _DUMMY_DIGEST
    if _DUMMY_DIGEST is None:
        _DUMMY_DIGEST = hash_password(secrets.token_urlsafe(24))
    verify_password(_DUMMY_DIGEST, password or "x")


def new_session_id() -> str:
    """192 bits of entropy, URL-safe. Opaque: the cookie carries no claims."""
    return secrets.token_urlsafe(24)


def new_csrf_token() -> str:
    return secrets.token_urlsafe(24)


def constant_time_equals(left: str, right: str) -> bool:
    return hmac.compare_digest((left or "").encode(), (right or "").encode())


def password_strength_error(password: str) -> Optional[str]:
    """Return a user-facing complaint, or None when acceptable.

    Deliberately short: length is the property that matters, and a long list of
    character-class rules pushes people towards `Passw0rd!` variants.
    """
    if not password or len(password) < MIN_PASSWORD_LENGTH:
        return f"Пароль должен содержать не менее {MIN_PASSWORD_LENGTH} символов."
    if password.strip() != password:
        return "Пароль не должен начинаться или заканчиваться пробелом."
    if len(set(password)) < 5:
        return "Пароль слишком однообразен."
    return None


def bootstrap_password_from_env() -> Optional[str]:
    """One-time bootstrap password, read from the environment and never stored.

    ``QF_DASHBOARD_BOOTSTRAP_PASSWORD`` lets a fresh deployment create its first
    administrator without an interactive shell. It is read once, hashed, and the
    caller is expected to unset it. There is no fallback value: if it is absent,
    no user is created and the dashboard says so.
    """
    value = os.getenv("QF_DASHBOARD_BOOTSTRAP_PASSWORD", "").strip()
    return value or None
