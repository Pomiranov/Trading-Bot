"""One-shot security bootstrap for all application entry points."""
from __future__ import annotations

import logging

from security.config_validation import run_startup_validation
from security.credential_vault import apply_vault_to_config
from security.logging_config import configure_logging
from security.secrets import get_secret_provider

logger = logging.getLogger(__name__)

_SECRET_KEY_MAP = {
    "DB_PASSWORD": ("db", "password"),
    "TINKOFF_TOKEN": ("tinkoff", "token"),
    "TINKOFF_ACCOUNT_ID": ("tinkoff", "account_id"),
    "BYBIT_API_KEY": ("bybit", "api_key"),
    "BYBIT_API_SECRET": ("bybit", "api_secret"),
    "TELEGRAM_TOKEN": ("telegram", "token"),
    "DASHBOARD_API_KEY": ("dashboard", "api_key"),
}


def apply_secret_provider_overrides(app_config) -> None:
    """Overlay secrets from Vault / Docker / env chain (highest priority first)."""
    provider = get_secret_provider()
    for key, (section, attr) in _SECRET_KEY_MAP.items():
        value = provider.get(key)
        if value:
            setattr(getattr(app_config, section), attr, value)


def bootstrap_security(app_config, *, service_name: str = "quantflow") -> None:
    configure_logging(
        level=app_config.log_level,
        log_file=app_config.logging.file_path or None,
        max_bytes=app_config.logging.max_bytes,
        backup_count=app_config.logging.backup_count,
    )
    apply_secret_provider_overrides(app_config)
    apply_vault_to_config(app_config)
    ok = run_startup_validation(app_config, exit_on_error=False)
    if not ok:
        logger.warning("%s started with configuration errors — review logs", service_name)
    else:
        logger.info("%s security bootstrap complete", service_name)