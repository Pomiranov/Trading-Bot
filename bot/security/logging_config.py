"""Centralized logging setup with redaction and optional rotation."""
from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from security.redaction import RedactingFilter
from security.request_context import RequestContextFilter

_CONFIGURED = False

_DEFAULT_FORMAT = (
    "%(asctime)s [%(levelname)s] %(name)s "
    "cid=%(correlation_id)s rid=%(request_id)s %(message)s"
)
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def configure_logging(
    level: str = "INFO",
    log_file: str | None = None,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
) -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    log_level = getattr(logging, level.upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(log_level)

    context_filter = RequestContextFilter()
    redact_filter = RedactingFilter()

    formatter = logging.Formatter(_DEFAULT_FORMAT, datefmt=_DATE_FORMAT)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    stream_handler.addFilter(context_filter)
    stream_handler.addFilter(redact_filter)
    root.addHandler(stream_handler)

    file_path = log_file or os.getenv("LOG_FILE", "").strip()
    if file_path:
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        file_handler.addFilter(context_filter)
        file_handler.addFilter(redact_filter)
        root.addHandler(file_handler)

    logging.captureWarnings(True)
    _CONFIGURED = True