"""Encrypted on-disk vault for broker and API credentials."""
from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Optional

from security.encryption import EncryptionError, SecretBox

logger = logging.getLogger(__name__)

VAULT_PATH = Path(__file__).parent.parent / "data" / "credential_vault.json"

SENSITIVE_ENV_KEYS = frozenset({
    "TINKOFF_TOKEN",
    "TINKOFF_ACCOUNT_ID",
    "BYBIT_API_KEY",
    "BYBIT_API_SECRET",
    "TELEGRAM_TOKEN",
    "DB_PASSWORD",
    "DASHBOARD_API_KEY",
})


class CredentialVault:
    def __init__(self, path: Path = VAULT_PATH, box: SecretBox | None = None) -> None:
        self._path = path
        self._box = box
        self._lock = threading.Lock()
        self._cache: dict[str, str] = {}
        if self._box is not None:
            self._load()

    @classmethod
    def try_create(cls, path: Path = VAULT_PATH) -> Optional["CredentialVault"]:
        try:
            box = SecretBox.from_env()
        except EncryptionError:
            return None
        if box is None:
            return None
        return cls(path=path, box=box)

    @property
    def enabled(self) -> bool:
        return self._box is not None

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            entries = raw.get("entries", {})
            for key, enc in entries.items():
                if isinstance(enc, str) and enc:
                    self._cache[key] = self._box.decrypt(enc)
        except (OSError, json.JSONDecodeError, EncryptionError) as exc:
            logger.error("Credential vault load failed: %s", exc)

    def _persist(self) -> None:
        if self._box is None:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        entries = {k: self._box.encrypt(v) for k, v in self._cache.items() if v}
        payload = {"version": 1, "entries": entries}
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(self._path)
        try:
            self._path.chmod(0o600)
        except OSError:
            pass

    def get(self, key: str) -> str | None:
        with self._lock:
            value = self._cache.get(key)
            return value if value else None

    def put(self, key: str, value: str) -> None:
        if self._box is None:
            raise EncryptionError("Credential vault is not enabled (set SECRETS_MASTER_KEY)")
        with self._lock:
            if value:
                self._cache[key] = value
            else:
                self._cache.pop(key, None)
            self._persist()
        logger.info("Credential vault updated: key=%s", key)

    def all_secrets(self) -> dict[str, str]:
        with self._lock:
            return dict(self._cache)


_vault: CredentialVault | None = None
_vault_initialized = False


def get_credential_vault() -> CredentialVault | None:
    global _vault, _vault_initialized
    if not _vault_initialized:
        _vault = CredentialVault.try_create()
        _vault_initialized = True
    return _vault


def apply_vault_to_config(app_config) -> None:
    """Overlay decrypted vault values onto the live AppConfig."""
    vault = get_credential_vault()
    if vault is None:
        return
    mapping = {
        "TINKOFF_TOKEN": ("tinkoff", "token"),
        "TINKOFF_ACCOUNT_ID": ("tinkoff", "account_id"),
        "BYBIT_API_KEY": ("bybit", "api_key"),
        "BYBIT_API_SECRET": ("bybit", "api_secret"),
        "TELEGRAM_TOKEN": ("telegram", "token"),
        "DB_PASSWORD": ("db", "password"),
        "DASHBOARD_API_KEY": ("dashboard", "api_key"),
    }
    for env_key, (section, attr) in mapping.items():
        value = vault.get(env_key)
        if value:
            setattr(getattr(app_config, section), attr, value)
            logger.debug("Config loaded from vault: %s", env_key)