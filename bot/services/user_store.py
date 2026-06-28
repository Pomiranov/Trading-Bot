"""User preferences and notification settings store (file-backed JSON)."""
from __future__ import annotations

import json
import logging
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_STORE_PATH = Path(__file__).parent.parent / "data" / "user_prefs.json"
_lock = threading.Lock()


@dataclass
class NotificationSettings:
    order_fill: bool = True
    new_signal: bool = True
    large_drawdown: bool = True
    profit_target: bool = True
    api_error: bool = True
    connection_lost: bool = True
    deposit: bool = True
    withdrawal: bool = True
    dividend: bool = True
    coupon: bool = True
    risk_limit: bool = True
    bot_started: bool = True
    bot_stopped: bool = True


@dataclass
class UserPrefs:
    chat_id: int
    username: Optional[str] = None
    timezone: str = "Europe/Moscow"
    language: str = "ru"
    currency: str = "RUB"
    default_broker: str = "tinkoff"
    notifications: NotificationSettings = field(default_factory=NotificationSettings)
    registered_at: Optional[str] = None
    last_seen: Optional[str] = None


class UserStore:
    def __init__(self, path: Path = _STORE_PATH) -> None:
        self._path = path
        self._data: dict[int, UserPrefs] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            for key, val in raw.items():
                chat_id = int(key)
                notif_data = val.pop("notifications", {})
                val.pop("chat_id", None)
                notif = NotificationSettings(**notif_data)
                self._data[chat_id] = UserPrefs(chat_id=chat_id, notifications=notif, **val)
        except Exception as exc:
            logger.error("Failed to load user prefs: %s", exc)

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            serializable = {
                str(chat_id): asdict(prefs)
                for chat_id, prefs in self._data.items()
            }
            self._path.write_text(
                json.dumps(serializable, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.error("Failed to save user prefs: %s", exc)

    def get(self, chat_id: int) -> UserPrefs:
        with _lock:
            if chat_id not in self._data:
                from datetime import datetime, timezone
                self._data[chat_id] = UserPrefs(
                    chat_id=chat_id,
                    registered_at=datetime.now(timezone.utc).isoformat(),
                )
                self._save()
            return self._data[chat_id]

    def save(self, prefs: UserPrefs) -> None:
        with _lock:
            from datetime import datetime, timezone
            prefs.last_seen = datetime.now(timezone.utc).isoformat()
            self._data[prefs.chat_id] = prefs
            self._save()

    def touch(self, chat_id: int, username: Optional[str] = None) -> UserPrefs:
        prefs = self.get(chat_id)
        if username:
            prefs.username = username
        self.save(prefs)
        return prefs

    def toggle_notification(self, chat_id: int, notif_key: str) -> bool:
        prefs = self.get(chat_id)
        current = getattr(prefs.notifications, notif_key, None)
        if current is None:
            raise ValueError(f"Unknown notification key: {notif_key}")
        setattr(prefs.notifications, notif_key, not current)
        self.save(prefs)
        return not current

    def get_users_with_notification(self, notif_key: str) -> list[int]:
        with _lock:
            return [
                chat_id
                for chat_id, prefs in self._data.items()
                if getattr(prefs.notifications, notif_key, False)
            ]

    def all_chat_ids(self) -> list[int]:
        with _lock:
            return list(self._data.keys())


user_store = UserStore()
