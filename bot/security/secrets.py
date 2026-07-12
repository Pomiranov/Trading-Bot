"""Secret provider abstraction — env, Docker secrets, optional Vault."""
from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from pathlib import Path

logger = logging.getLogger(__name__)

DOCKER_SECRETS_DIR = Path("/run/secrets")


class SecretProvider(ABC):
    @abstractmethod
    def get(self, key: str) -> str | None:
        """Return secret value or None if not available."""


class EnvSecretProvider(SecretProvider):
    def get(self, key: str) -> str | None:
        value = os.getenv(key)
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class DockerSecretProvider(SecretProvider):
    """Read secrets mounted at /run/secrets/<key> (Docker Swarm / Compose secrets)."""

    def __init__(self, base_dir: Path = DOCKER_SECRETS_DIR) -> None:
        self._base = base_dir

    def get(self, key: str) -> str | None:
        path = self._base / key.lower()
        if not path.is_file():
            path = self._base / key
        if not path.is_file():
            return None
        try:
            value = path.read_text(encoding="utf-8").strip()
            return value or None
        except OSError as exc:
            logger.warning("Docker secret read failed for %s: %s", key, exc)
            return None


class VaultSecretProvider(SecretProvider):
    """
    HashiCorp Vault KV read (optional).

    Requires VAULT_ADDR, VAULT_TOKEN, and VAULT_SECRET_PATH (e.g. secret/data/quantflow).
    Falls back silently when not configured.
    """

    def __init__(self) -> None:
        self._addr = os.getenv("VAULT_ADDR", "").strip().rstrip("/")
        self._token = os.getenv("VAULT_TOKEN", "").strip()
        self._path = os.getenv("VAULT_SECRET_PATH", "").strip().strip("/")

    def _configured(self) -> bool:
        return bool(self._addr and self._token and self._path)

    def get(self, key: str) -> str | None:
        if not self._configured():
            return None
        try:
            import json
            import urllib.request

            url = f"{self._addr}/v1/{self._path}"
            req = urllib.request.Request(
                url,
                headers={"X-Vault-Token": self._token},
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            data = payload.get("data", {}).get("data", {})
            value = data.get(key)
            if value is None:
                return None
            return str(value).strip() or None
        except Exception as exc:
            logger.warning("Vault secret read failed for %s: %s", key, exc)
            return None


class ChainedSecretProvider(SecretProvider):
    """First non-empty value wins (Vault → Docker → Env by default)."""

    def __init__(self, providers: list[SecretProvider] | None = None) -> None:
        self._providers = providers or [
            VaultSecretProvider(),
            DockerSecretProvider(),
            EnvSecretProvider(),
        ]

    def get(self, key: str) -> str | None:
        for provider in self._providers:
            value = provider.get(key)
            if value:
                return value
        return None


_default_provider: ChainedSecretProvider | None = None


def get_secret_provider() -> ChainedSecretProvider:
    global _default_provider
    if _default_provider is None:
        _default_provider = ChainedSecretProvider()
    return _default_provider


def resolve_secret(key: str, default: str = "") -> str:
    return get_secret_provider().get(key) or default