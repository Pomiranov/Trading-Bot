"""Log redaction — prevents secrets from appearing in log output."""
from __future__ import annotations

import logging
import re
from typing import Pattern

_REDACTION_PATTERNS: list[tuple[Pattern[str], str]] = [
    (re.compile(r"\bt\.[A-Za-z0-9_-]{20,}\b"), "t.[REDACTED]"),
    (re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{30,}\b"), "[REDACTED_TELEGRAM_TOKEN]"),
    (re.compile(r"(?i)(Bearer\s+)[A-Za-z0-9._-]+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(api[_-]?key\s*[=:]\s*)[^\s,;'\"]+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(api[_-]?secret\s*[=:]\s*)[^\s,;'\"]+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(password\s*[=:]\s*)[^\s,;'\"]+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(token\s*[=:]\s*)[^\s,;'\"]+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(token=)t\.[A-Za-z0-9_-]+"), r"\1[REDACTED]"),
    (re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"), "[REDACTED_JWT]"),
    (re.compile(r"(?i)(postgresql://)[^@\s]+@"), r"\1[REDACTED]@"),
]


def redact_text(text: str) -> str:
    if not text:
        return text
    result = text
    for pattern, replacement in _REDACTION_PATTERNS:
        result = pattern.sub(replacement, result)
    return result


class RedactingFilter(logging.Filter):
    """Logging filter that redacts sensitive substrings from records."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_text(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: redact_text(str(v)) for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    redact_text(arg) if isinstance(arg, str) else arg
                    for arg in record.args
                )
        return True