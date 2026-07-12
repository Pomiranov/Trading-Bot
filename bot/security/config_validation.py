"""Startup configuration validation — fail-fast on critical misconfigurations."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ValidationIssue:
    level: str  # "error" | "warning"
    code: str
    message: str


def validate_config(app_config) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    if not app_config.db.password:
        issues.append(ValidationIssue(
            "error", "DB_PASSWORD_MISSING",
            "DB_PASSWORD is not set — database connection will fail",
        ))

    if app_config.telegram.token:
        if not app_config.telegram.chat_id and not app_config.telegram.allowed_chat_ids:
            issues.append(ValidationIssue(
                "error", "TELEGRAM_AUTH_UNCONFIGURED",
                "TELEGRAM_CHAT_ID or TELEGRAM_ALLOWED_IDS required when TELEGRAM_TOKEN is set",
            ))

    if app_config.dashboard.host in ("0.0.0.0", "::"):
        if not app_config.dashboard.api_key:
            issues.append(ValidationIssue(
                "error", "DASHBOARD_EXPOSED_NO_API_KEY",
                "DASHBOARD_HOST binds all interfaces but DASHBOARD_API_KEY is not set",
            ))

    master_key = getattr(app_config.secrets, "master_key", "")
    if master_key:
        if not re.fullmatch(r"[0-9a-fA-F]{64}", master_key):
            if len(master_key) < 32:
                issues.append(ValidationIssue(
                    "error", "SECRETS_MASTER_KEY_INVALID",
                    "SECRETS_MASTER_KEY must be 64-char hex (32 bytes) or valid base64",
                ))

    if app_config.tinkoff.token and not app_config.tinkoff.sandbox:
        issues.append(ValidationIssue(
            "warning", "TINKOFF_LIVE_MODE",
            "TINKOFF_SANDBOX=false — live trading enabled",
        ))

    if app_config.bybit.api_key and not app_config.bybit.testnet:
        issues.append(ValidationIssue(
            "warning", "BYBIT_MAINNET",
            "BYBIT_TESTNET=false — mainnet API keys in use",
        ))

    return issues


def run_startup_validation(app_config, *, exit_on_error: bool = False) -> bool:
    issues = validate_config(app_config)
    has_errors = False
    for issue in issues:
        if issue.level == "error":
            has_errors = True
            logger.error("[%s] %s", issue.code, issue.message)
        else:
            logger.warning("[%s] %s", issue.code, issue.message)

    if has_errors and exit_on_error:
        raise SystemExit(1)
    return not has_errors