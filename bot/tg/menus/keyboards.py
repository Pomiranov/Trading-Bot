"""All inline and reply keyboard builders for the trading platform bot."""
from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton


# ── Navigation helpers ────────────────────────────────────────────────────────

def nav_row(back: str | None = "m_main", refresh: str | None = None) -> list[InlineKeyboardButton]:
    row: list[InlineKeyboardButton] = []
    if back:
        row.append(InlineKeyboardButton("◀ Назад", callback_data=back))
    if refresh:
        row.append(InlineKeyboardButton("🔄 Обновить", callback_data=refresh))
    row.append(InlineKeyboardButton("🏠 Главная", callback_data="m_main"))
    return row


# ── Main menu ─────────────────────────────────────────────────────────────────

MAIN_MENU = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("📊 Dashboard",    callback_data="m_dashboard"),
        InlineKeyboardButton("💼 Портфель",     callback_data="m_portfolio"),
    ],
    [
        InlineKeyboardButton("📈 Позиции",      callback_data="m_positions"),
        InlineKeyboardButton("📑 Заявки",       callback_data="m_orders"),
    ],
    [
        InlineKeyboardButton("📜 Операции",     callback_data="m_operations"),
        InlineKeyboardButton("💰 Баланс",       callback_data="m_balance"),
    ],
    [
        InlineKeyboardButton("📊 Аналитика",    callback_data="m_analytics"),
        InlineKeyboardButton("📈 Статистика",   callback_data="m_statistics"),
    ],
    [
        InlineKeyboardButton("🤖 Торговый бот", callback_data="m_trading_bot"),
        InlineKeyboardButton("📡 Сигналы",      callback_data="m_signals"),
    ],
    [
        InlineKeyboardButton("🔔 Уведомления",  callback_data="m_notifications"),
        InlineKeyboardButton("⚙ Настройки",    callback_data="m_settings"),
    ],
    [
        InlineKeyboardButton("👤 Аккаунт",      callback_data="m_account"),
        InlineKeyboardButton("❓ Помощь",       callback_data="m_help"),
    ],
])


def main_menu() -> InlineKeyboardMarkup:
    return MAIN_MENU


# ── Dashboard ─────────────────────────────────────────────────────────────────

def dashboard_keyboard(broker_id: str = "tinkoff") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💼 Портфель",   callback_data="m_portfolio"),
            InlineKeyboardButton("📈 Позиции",    callback_data="m_positions"),
        ],
        [
            InlineKeyboardButton("📊 Статистика", callback_data="m_statistics"),
            InlineKeyboardButton("🔄 Обновить",   callback_data="dash_refresh"),
        ],
        [InlineKeyboardButton("🏠 Главная", callback_data="m_main")],
    ])


# ── Portfolio ─────────────────────────────────────────────────────────────────

def portfolio_keyboard(has_positions: bool = True) -> InlineKeyboardMarkup:
    rows = []
    if has_positions:
        rows.append([
            InlineKeyboardButton("📈 Все позиции",   callback_data="m_positions"),
            InlineKeyboardButton("📊 Аналитика",     callback_data="m_analytics"),
        ])
    rows.append([
        InlineKeyboardButton("🔄 Обновить", callback_data="port_refresh"),
        InlineKeyboardButton("🏠 Главная",  callback_data="m_main"),
    ])
    return InlineKeyboardMarkup(rows)


# ── Positions ─────────────────────────────────────────────────────────────────

def positions_keyboard(page: int = 0, total_pages: int = 1) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if total_pages > 1:
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton("◀", callback_data=f"pos_pg_{page - 1}"))
        nav.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="pos_noop"))
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton("▶", callback_data=f"pos_pg_{page + 1}"))
        rows.append(nav)
    rows.append([
        InlineKeyboardButton("🔄 Обновить", callback_data="pos_refresh"),
        InlineKeyboardButton("🏠 Главная",  callback_data="m_main"),
    ])
    return InlineKeyboardMarkup(rows)


def position_detail_keyboard(ticker: str, broker_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💸 Продать",   callback_data=f"trade_sell_{broker_id}_{ticker}"),
            InlineKeyboardButton("📜 История",   callback_data=f"pos_hist_{ticker}"),
        ],
        [
            InlineKeyboardButton("◀ Позиции",   callback_data="m_positions"),
            InlineKeyboardButton("🏠 Главная",   callback_data="m_main"),
        ],
    ])


# ── Orders ────────────────────────────────────────────────────────────────────

def orders_filter_keyboard(active_filter: str = "active") -> InlineKeyboardMarkup:
    def _mark(key: str) -> str:
        return f"✅ {key.capitalize()}" if active_filter == key else key.capitalize()

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(_mark("active"),    callback_data="ord_filter_active"),
            InlineKeyboardButton(_mark("filled"),    callback_data="ord_filter_filled"),
            InlineKeyboardButton(_mark("cancelled"), callback_data="ord_filter_cancelled"),
        ],
        [
            InlineKeyboardButton("🔄 Обновить", callback_data="ord_refresh"),
            InlineKeyboardButton("🏠 Главная",  callback_data="m_main"),
        ],
    ])


def order_action_keyboard(order_id: str, broker_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Отменить заявку", callback_data=f"ord_cancel_{broker_id}_{order_id}")],
        [
            InlineKeyboardButton("◀ Заявки", callback_data="m_orders"),
            InlineKeyboardButton("🏠 Главная", callback_data="m_main"),
        ],
    ])


# ── Operations ────────────────────────────────────────────────────────────────

def operations_keyboard(page: int = 0, total_pages: int = 1) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if total_pages > 1:
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton("◀", callback_data=f"ops_pg_{page - 1}"))
        nav.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="ops_noop"))
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton("▶", callback_data=f"ops_pg_{page + 1}"))
        rows.append(nav)
    rows.append([
        InlineKeyboardButton("🔄 Обновить", callback_data="ops_refresh"),
        InlineKeyboardButton("🏠 Главная",  callback_data="m_main"),
    ])
    return InlineKeyboardMarkup(rows)


# ── Statistics ────────────────────────────────────────────────────────────────

def statistics_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Обновить",  callback_data="stat_refresh"),
            InlineKeyboardButton("🏠 Главная",   callback_data="m_main"),
        ],
    ])


# ── Trading ───────────────────────────────────────────────────────────────────

def trading_menu_keyboard(broker_id: str = "tinkoff") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🟢 Купить",         callback_data=f"trade_buy_{broker_id}"),
            InlineKeyboardButton("🔴 Продать",        callback_data=f"trade_sell_{broker_id}"),
        ],
        [
            InlineKeyboardButton("📑 Мои заявки",     callback_data="m_orders"),
            InlineKeyboardButton("📈 Позиции",        callback_data="m_positions"),
        ],
        [InlineKeyboardButton("🏠 Главная", callback_data="m_main")],
    ])


def confirm_trade_keyboard(
    direction: str, broker_id: str, figi: str, quantity: int, price: str = "market"
) -> InlineKeyboardMarkup:
    confirm_data = f"trade_confirm_{direction}_{broker_id}_{figi}_{quantity}_{price}"
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Подтвердить", callback_data=confirm_data),
            InlineKeyboardButton("❌ Отмена",      callback_data="m_main"),
        ],
    ])


# ── Trading bot ───────────────────────────────────────────────────────────────

def trading_bot_keyboard(status: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if status == "RUNNING":
        rows.append([
            InlineKeyboardButton("⏸ Пауза",     callback_data="bot_pause"),
            InlineKeyboardButton("⏹ Остановить", callback_data="bot_stop"),
        ])
    elif status == "PAUSED":
        rows.append([
            InlineKeyboardButton("▶ Продолжить", callback_data="bot_resume"),
            InlineKeyboardButton("⏹ Остановить", callback_data="bot_stop"),
        ])
    else:
        rows.append([InlineKeyboardButton("▶ Запустить", callback_data="bot_start")])

    rows.append([
        InlineKeyboardButton("📊 Статус",     callback_data="bot_status"),
        InlineKeyboardButton("📜 Логи",       callback_data="bot_logs"),
    ])
    rows.append([
        InlineKeyboardButton("📡 Сигналы",    callback_data="m_signals"),
        InlineKeyboardButton("🏠 Главная",    callback_data="m_main"),
    ])
    return InlineKeyboardMarkup(rows)


# ── Signals ───────────────────────────────────────────────────────────────────

def signals_keyboard(active_filter: str = "all") -> InlineKeyboardMarkup:
    def _mark(key: str) -> str:
        return f"✅ {key.capitalize()}" if active_filter == key else key.capitalize()

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(_mark("all"),      callback_data="sig_filter_all"),
            InlineKeyboardButton(_mark("active"),   callback_data="sig_filter_active"),
        ],
        [
            InlineKeyboardButton("🔎 Запрос",       callback_data="sig_query"),
            InlineKeyboardButton("🔄 Обновить",     callback_data="sig_refresh"),
        ],
        [InlineKeyboardButton("🏠 Главная", callback_data="m_main")],
    ])


# ── Notifications ─────────────────────────────────────────────────────────────

_NOTIF_LABELS = {
    "order_fill":      "✔ Исполнение заявки",
    "new_signal":      "📡 Новый сигнал",
    "large_drawdown":  "📉 Большая просадка",
    "profit_target":   "🎯 Цель по прибыли",
    "api_error":       "🔴 Ошибка API",
    "connection_lost": "📵 Потеря соединения",
    "deposit":         "💵 Пополнение",
    "withdrawal":      "💸 Вывод средств",
    "dividend":        "💰 Дивиденды",
    "coupon":          "🏦 Купоны",
    "risk_limit":      "⚠ Лимиты риска",
    "bot_started":     "▶ Бот запущен",
    "bot_stopped":     "⏹ Бот остановлен",
}


def notifications_keyboard(settings) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for key, label in _NOTIF_LABELS.items():
        is_on = getattr(settings, key, False)
        icon = "🔔" if is_on else "🔕"
        rows.append([InlineKeyboardButton(
            f"{icon} {label}",
            callback_data=f"notif_toggle_{key}",
        )])
    rows.append([InlineKeyboardButton("🏠 Главная", callback_data="m_main")])
    return InlineKeyboardMarkup(rows)


# ── Settings ──────────────────────────────────────────────────────────────────

def settings_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔗 Брокеры",      callback_data="set_brokers"),
            InlineKeyboardButton("🔑 API токены",   callback_data="set_tokens"),
        ],
        [
            InlineKeyboardButton("🕐 Часовой пояс", callback_data="set_timezone"),
            InlineKeyboardButton("💱 Валюта",       callback_data="set_currency"),
        ],
        [
            InlineKeyboardButton("⚠ Лимиты риска", callback_data="set_risk"),
            InlineKeyboardButton("🔁 Интервал",     callback_data="set_interval"),
        ],
        [
            InlineKeyboardButton("🛡 Безопасность", callback_data="set_security"),
            InlineKeyboardButton("🏠 Главная",      callback_data="m_main"),
        ],
    ])


def broker_settings_keyboard(brokers) -> InlineKeyboardMarkup:
    rows = []
    for info in brokers:
        icon = "🟢" if info.is_connected else ("🟡" if info.is_configured else "⚪")
        rows.append([InlineKeyboardButton(
            f"{icon} {info.name}",
            callback_data=f"set_broker_{info.broker_id}",
        )])
    rows.append([InlineKeyboardButton("◀ Настройки", callback_data="m_settings")])
    return InlineKeyboardMarkup(rows)


def tinkoff_settings_keyboard(has_token: bool, has_account: bool) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            f"{'✅' if has_token else '❌'} API Токен",
            callback_data="set_tinkoff_token",
        )],
        [InlineKeyboardButton(
            f"{'✅' if has_account else '❌'} ID счёта",
            callback_data="set_tinkoff_account",
        )],
        [
            InlineKeyboardButton("◀ Брокеры",  callback_data="set_brokers"),
            InlineKeyboardButton("🏠 Главная", callback_data="m_main"),
        ],
    ])


# ── Account ───────────────────────────────────────────────────────────────────

def account_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 Подключённые счета", callback_data="acc_accounts")],
        [InlineKeyboardButton("🏠 Главная", callback_data="m_main")],
    ])


# ── Cancel button ─────────────────────────────────────────────────────────────

CANCEL_KB = InlineKeyboardMarkup([
    [InlineKeyboardButton("❌ Отмена", callback_data="m_main")],
])
