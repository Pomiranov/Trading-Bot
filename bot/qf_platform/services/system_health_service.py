"""System health metrics for platform dashboard."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from typing import Optional

from sqlalchemy import Engine, text

from config import config

logger = logging.getLogger(__name__)


class SystemHealthService:
    def __init__(self, engine: Optional[Engine] = None):
        self._engine = engine

    def _cpu_percent(self) -> float:
        try:
            import psutil
            return round(psutil.cpu_percent(interval=0.1), 1)
        except ImportError:
            return 0.0

    def _ram_usage(self) -> dict:
        try:
            import psutil
            mem = psutil.virtual_memory()
            return {
                "used_mb": round(mem.used / 1024 / 1024, 1),
                "total_mb": round(mem.total / 1024 / 1024, 1),
                "percent": round(mem.percent, 1),
            }
        except ImportError:
            return {"used_mb": 0, "total_mb": 0, "percent": 0}

    def _db_status(self) -> dict:
        if self._engine is None:
            return {"status": "offline", "connected": False}
        try:
            with self._engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            size_rows = []
            try:
                with self._engine.connect() as conn:
                    r = conn.execute(text(
                        "SELECT pg_database_size(current_database()) AS size"
                    ))
                    size_rows = r.fetchone()
            except Exception:
                pass
            return {
                "status": "online",
                "connected": True,
                "host": config.db.host,
                "size_mb": round(int(size_rows[0]) / 1024 / 1024, 1) if size_rows else 0,
            }
        except Exception as exc:
            return {"status": "error", "connected": False, "error": str(exc)}

    def _redis_status(self) -> dict:
        try:
            import redis
            host = os.getenv("REDIS_HOST", "localhost")
            port = int(os.getenv("REDIS_PORT", "6379"))
            r = redis.Redis(host=host, port=port, socket_connect_timeout=1)
            r.ping()
            return {"status": "online", "connected": True, "host": f"{host}:{port}"}
        except Exception:
            return {"status": "offline", "connected": False}

    def _docker_status(self) -> dict:
        try:
            result = subprocess.run(
                ["docker", "ps", "--format", "{{.Names}}"],
                capture_output=True, text=True, timeout=3,
            )
            containers = [c for c in result.stdout.strip().split("\n") if c]
            return {"status": "online" if result.returncode == 0 else "offline", "containers": containers}
        except Exception:
            return {"status": "unknown", "containers": []}

    def _telegram_status(self) -> dict:
        configured = bool(config.telegram.token)
        return {"status": "configured" if configured else "not_configured", "connected": configured}

    def _api_status(self) -> dict:
        return {"status": "online", "port": config.dashboard.port}

    def get_health(self) -> dict:
        return {
            "cpu_percent": self._cpu_percent(),
            "ram": self._ram_usage(),
            "database": self._db_status(),
            "redis": self._redis_status(),
            "docker": self._docker_status(),
            "telegram": self._telegram_status(),
            "api": self._api_status(),
            "disk_free_gb": round(shutil.disk_usage("/").free / 1024 ** 3, 1),
        }