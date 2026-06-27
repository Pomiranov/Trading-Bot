"""Help handler — command reference and platform guide."""
from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from tg.menus.keyboards import InlineKeyboardMarkup, InlineKeyboardButton
from tg.middlewares.auth import require_auth

_HELP_TEXT = """❓ <b>Помощь</b>
─────────────────────────
<b>Команды:</b>
/start       — главное меню
/dashboard   — обзор портфеля
/portfolio   — полный портфель
/positions   — открытые позиции
/orders      — заявки
/operations  — история операций
/balance     — баланс
/statistics  — статистика
/signal &lt;TICKER&gt; — сигнал по тикеру
/cancel      — отмена текущего действия

─────────────────────────
<b>Навигация:</b>
Используйте кнопки меню для навигации.
🔄 Обновить — обновить данные
🏠 Главная — вернуться в главное меню
◀ Назад — предыдущий экран

─────────────────────────
<b>Торговля:</b>
Перейдите в раздел <b>🔄 Торговля</b>.
Введите тикер и количество лотов.
Заявки требуют подтверждения.

─────────────────────────
<b>Безопасность:</b>
🔒 Бот работает только с авторизованными
пользователями.
Токены хранятся зашифровано в .env файле.
Критические операции требуют подтверждения.

─────────────────────────
<b>Поддерживаемые брокеры:</b>
🟢 Т-Банк (Tinkoff Invest)
⚪ Finam (в разработке)"""

_KB = InlineKeyboardMarkup([
    [InlineKeyboardButton("🏠 Главное меню", callback_data="m_main")],
])


async def _render(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not await require_auth(update, context):
        if query:
            await query.answer()
        return

    if query:
        await query.answer()
        await query.edit_message_text(_HELP_TEXT, reply_markup=_KB, parse_mode="HTML")
    else:
        await update.effective_message.reply_html(_HELP_TEXT, reply_markup=_KB)


async def cb_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _render(update, context)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _render(update, context)
