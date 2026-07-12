"""AES-256-GCM encryption for secrets at rest."""
from __future__ import annotations

import base64
import logging
import os
import secrets
from typing import Optional

logger = logging.getLogger(__name__)

_NONCE_BYTES = 12
_KEY_BYTES = 32


class EncryptionError(RuntimeError):
    pass


def _decode_master_key(raw: str) -> bytes:
    text = raw.strip()
    if not text:
        raise EncryptionError("SECRETS_MASTER_KEY is empty")

    try:
        if len(text) == 64 and all(c in "0123456789abcdefABCDEF" for c in text):
            key = bytes.fromhex(text)
        else:
            key = base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))
    except (ValueError, base64.binascii.Error) as exc:
        raise EncryptionError("SECRETS_MASTER_KEY must be 32-byte hex or base64") from exc

    if len(key) != _KEY_BYTES:
        raise EncryptionError(f"SECRETS_MASTER_KEY must be {_KEY_BYTES} bytes, got {len(key)}")
    return key


class SecretBox:
    """Encrypt/decrypt UTF-8 strings with AES-256-GCM."""

    def __init__(self, master_key: str) -> None:
        self._key = _decode_master_key(master_key)

    @classmethod
    def from_env(cls) -> Optional["SecretBox"]:
        raw = os.getenv("SECRETS_MASTER_KEY", "").strip()
        if not raw:
            return None
        try:
            return cls(raw)
        except EncryptionError as exc:
            logger.error("%s", exc)
            raise

    def encrypt(self, plaintext: str) -> str:
        if plaintext == "":
            return ""
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        except ImportError as exc:
            raise EncryptionError(
                "cryptography package required for encryption. pip install cryptography"
            ) from exc

        nonce = secrets.token_bytes(_NONCE_BYTES)
        aesgcm = AESGCM(self._key)
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        blob = nonce + ciphertext
        return base64.urlsafe_b64encode(blob).decode("ascii")

    def decrypt(self, token: str) -> str:
        if token == "":
            return ""
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        except ImportError as exc:
            raise EncryptionError(
                "cryptography package required for decryption. pip install cryptography"
            ) from exc

        try:
            blob = base64.urlsafe_b64decode(token.encode("ascii"))
        except (ValueError, base64.binascii.Error) as exc:
            raise EncryptionError("Invalid encrypted blob encoding") from exc

        if len(blob) < _NONCE_BYTES + 16:
            raise EncryptionError("Encrypted blob too short")

        nonce, ciphertext = blob[:_NONCE_BYTES], blob[_NONCE_BYTES:]
        aesgcm = AESGCM(self._key)
        try:
            plain = aesgcm.decrypt(nonce, ciphertext, None)
        except Exception as exc:
            raise EncryptionError("Decryption failed — wrong key or corrupted data") from exc
        return plain.decode("utf-8")