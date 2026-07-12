"""Unified credential persistence — .env and/or encrypted vault."""
from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import set_key

from security.audit import audit_record
from security.credential_vault import SENSITIVE_ENV_KEYS, get_credential_vault

logger = logging.getLogger(__name__)

_ENV_FILE = Path(__file__).parent.parent.parent / ".env"


def _apply_to_runtime(key: str, value: str, app_config) -> None:
    os.environ[key] = value
    mapping = {
        "TINKOFF_TOKEN": lambda: setattr(app_config.tinkoff, "token", value),
        "TINKOFF_ACCOUNT_ID": lambda: setattr(app_config.tinkoff, "account_id", value),
        "BYBIT_API_KEY": lambda: setattr(app_config.bybit, "api_key", value),
        "BYBIT_API_SECRET": lambda: setattr(app_config.bybit, "api_secret", value),
        "TELEGRAM_TOKEN": lambda: setattr(app_config.telegram, "token", value),
        "DB_PASSWORD": lambda: setattr(app_config.db, "password", value),
        "DASHBOARD_API_KEY": lambda: setattr(app_config.dashboard, "api_key", value),
    }
    applier = mapping.get(key)
    if applier:
        applier()


def persist_credential(
    key: str,
    value: str,
    app_config,
    *,
    actor_type: str = "system",
    actor_id: str | None = None,
    client_ip: str | None = None,
) -> None:
    """
    Store a credential in the encrypted vault (if enabled) and .env for non-sensitive
    keys or when vault is disabled.
    """
    vault = get_credential_vault()
    stored_in_vault = False

    if vault is not None and vault.enabled and key in SENSITIVE_ENV_KEYS:
        vault.put(key, value)
        stored_in_vault = True
        _apply_to_runtime(key, value, app_config)
    else:
        _ENV_FILE.touch(exist_ok=True)
        set_key(str(_ENV_FILE), key, value, quote_mode="never")
        _apply_to_runtime(key, value, app_config)

    audit_record(
        event_type="credential.update",
        actor_type=actor_type,
        actor_id=actor_id,
        resource_type="credential",
        resource_id=key,
        outcome="success",
        client_ip=client_ip,
        metadata={"vault": stored_in_vault},
    )
    logger.info("Credential persisted: key=%s vault=%s", key, stored_in_vault)