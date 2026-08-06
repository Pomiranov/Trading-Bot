"""Help handler — command reference and platform guide."""
from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from tg.menus.keyboards import InlineKeyboardMarkup, InlineKeyboardButton
from tg.middlewares.auth import require_auth

_HELP_TEXT = """❓ <b>Справочный центр QuantFlow</b>
─────────────────────────────
<b>🤖 Auto Trading:</b>
  /status      — статус торгового движка
  Раздел <b>Auto Trading</b> — запуск, пауза, стоп
  Signal Engine + Paper Engine работают синхронно

<b>📡 Сигналы:</b>
  /signal      — список последних сигналов
  /signal SBER — сигнал по тикеру
  Каждый сигнал: актив, тип, SL, TP, R:R, Confidence, причина

<b>📊 Paper Trading:</b>
  /paper       — виртуальный торговый счёт
  Автоматические сделки на основе сигналов
  SL/TP мониторинг каждые 30 секунд

<b>💼 Портфель и позиции:</b>
  /portfolio   — портфель брокера
  /positions   — открытые позиции
  /orders      — заявки
  /operations  — история операций
  /balance     — баланс счёта

<b>📊 Аналитика:</b>
  Sharpe Ratio, Sortino, Drawdown
  Win Rate, Profit Factor, ROI
  Разбивка по стратегиям
  Лучшие/худшие сделки

─────────────────────────────
<b>Навигация:</b>
  🏠 Главная — главное меню
  🔄 Обновить — актуальные данные
  ◀ Назад — предыдущий экран
  ⚡ Генерировать — запуск анализа рынка

─────────────────────────────
<b>Управление риском:</b>
  Макс. позиций: настраивается в .env
  Дневной лимит убытков: RISK_MAX_DAILY_LOSS_PCT
  ATR-стоп, Trailing Stop автоматически

─────────────────────────────
<b>Поддерживаемые брокеры:</b>
  🟢 Т-Банк Инвест (Tinkoff)  — sandbox режим
  ⚪ Bybit — настраивается
  ⚪ Finam — в разработке"""

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
