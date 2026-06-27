"""Rich Telegram message builders for each platform section."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from broker.base import (
    BrokerBalance,
    BrokerOperation,
    BrokerOrder,
    BrokerPortfolio,
    BrokerPosition,
    BrokerInfo,
    OrderDirection,
    OrderStatus,
    OperationType,
)
from services.statistics_service import FullStatistics
from services.bot_engine import BotStatus
from tg.formatters.numbers import (
    fmt_money, fmt_pct, fmt_pnl, fmt_float, fmt_datetime, fmt_date,
    fmt_ratio, pnl_arrow, instrument_type_emoji, operation_type_emoji,
)

_SEP = "─" * 28


def build_dashboard(
    portfolio: Optional[BrokerPortfolio],
    stats: Optional[FullStatistics],
    broker_info: BrokerInfo,
    bot_status: BotStatus,
) -> str:
    now = datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M UTC")
    broker_icon = "🟢" if broker_info.is_connected else "🔴"
    bot_icon = "🟢" if bot_status == BotStatus.RUNNING else ("⏸" if bot_status == BotStatus.PAUSED else "⏹")

    lines = [
        "📊 <b>Dashboard</b>",
        _SEP,
    ]

    if portfolio:
        pnl_icon = pnl_arrow(portfolio.total_yield)
        lines += [
            f"💼 <b>Портфель:</b> {fmt_money(portfolio.total_value, '₽')}",
            f"📈 <b>Доходность:</b> {fmt_pnl(portfolio.total_yield)} ({fmt_pct(portfolio.total_yield_pct)})",
            f"📌 <b>Позиций:</b> {portfolio.positions_count}",
        ]
    else:
        lines.append("💼 Портфель: данные недоступны")

    lines.append(_SEP)

    if stats and stats.has_data:
        lines += [
            f"📅 <b>Сегодня:</b> {fmt_pnl(stats.pnl_today)}",
            f"📆 <b>Неделя:</b>  {fmt_pnl(stats.pnl_week)}",
            f"🗓 <b>Месяц:</b>   {fmt_pnl(stats.pnl_month)}",
            f"📊 <b>Всё время:</b> {fmt_pnl(stats.pnl_all_time)}",
            f"✅ <b>Сделок:</b> {stats.total_trades} | Win Rate: {fmt_pct(stats.win_rate)}",
        ]
    else:
        lines.append("📊 Статистика: нет данных")

    lines += [
        _SEP,
        f"{broker_icon} <b>Брокер:</b> {broker_info.name}",
        f"{bot_icon} <b>Бот:</b> {bot_status.value}",
        f"🕐 <i>Обновлено: {now}</i>",
    ]
    return "\n".join(lines)


def build_portfolio(portfolio: BrokerPortfolio) -> str:
    lines = [
        "💼 <b>Портфель</b>",
        _SEP,
        f"💰 <b>Стоимость:</b> {fmt_money(portfolio.total_value, '₽')}",
        f"📈 <b>Доходность:</b> {fmt_pnl(portfolio.total_yield)} ({fmt_pct(portfolio.total_yield_pct)})",
        f"📌 <b>Позиций:</b> {portfolio.positions_count}",
        _SEP,
    ]

    if not portfolio.positions:
        lines += [
            "🗂 <i>Портфель пуст</i>",
            "",
            "Для начала торговли перейдите в раздел",
            "🔄 <b>Торговля</b> или настройте <b>Торговый бот</b>",
        ]
        return "\n".join(lines)

    type_groups: dict[str, list[BrokerPosition]] = {}
    for pos in portfolio.positions:
        itype = pos.instrument_type
        type_groups.setdefault(itype, []).append(pos)

    type_labels = {
        "stock": "📈 Акции", "share": "📈 Акции",
        "etf": "🧺 ETF", "bond": "📊 Облигации",
        "currency": "💱 Валюта", "crypto": "₿ Крипто",
    }

    for itype, positions in sorted(type_groups.items()):
        label = type_labels.get(itype, f"📌 {itype.capitalize()}")
        group_value = sum(p.current_value for p in positions)
        pct_of_total = (group_value / portfolio.total_value * 100) if portfolio.total_value > 0 else 0
        lines.append(f"\n{label} <i>({fmt_pct(pct_of_total)} | {fmt_money(group_value, '₽')})</i>")
        for pos in sorted(positions, key=lambda p: p.current_value, reverse=True):
            pnl_color = "🟢" if pos.unrealized_pnl >= 0 else "🔴"
            lines.append(
                f"  {pnl_color} <b>{pos.ticker}</b> — {fmt_money(pos.current_value, '₽')} "
                f"({fmt_pct(pos.unrealized_pnl_pct)})"
            )

    return "\n".join(lines)


def build_positions_page(positions: list[BrokerPosition], page: int = 0, per_page: int = 5) -> str:
    if not positions:
        return (
            "📈 <b>Позиции</b>\n"
            + _SEP + "\n"
            "🗂 <i>Открытых позиций нет</i>\n\n"
            "Торговый бот не имеет активных позиций\n"
            "или портфель ещё не загружен."
        )

    start = page * per_page
    page_items = positions[start: start + per_page]
    total_pages = (len(positions) + per_page - 1) // per_page

    lines = [
        f"📈 <b>Позиции</b> ({len(positions)} шт.)",
        f"Страница {page + 1}/{total_pages}",
        _SEP,
    ]

    for pos in page_items:
        pnl_sign = "🟢" if pos.unrealized_pnl >= 0 else "🔴"
        lines += [
            f"\n{instrument_type_emoji(pos.instrument_type)} <b>{pos.ticker}</b> — {pos.name}",
            f"  Кол-во: {fmt_float(pos.quantity)} ({fmt_float(pos.quantity_lots)} лотов)",
            f"  Средняя цена: {fmt_money(pos.average_price, pos.currency, 4)}",
            f"  Текущая цена: {fmt_money(pos.current_price, pos.currency, 4)}",
            f"  Стоимость: {fmt_money(pos.current_value, '₽')}",
            f"  {pnl_sign} PnL: {fmt_pnl(pos.unrealized_pnl)} ({fmt_pct(pos.unrealized_pnl_pct)})",
        ]

    return "\n".join(lines)


def build_position_detail(pos: BrokerPosition) -> str:
    pnl_icon = "🟢" if pos.unrealized_pnl >= 0 else "🔴"
    return "\n".join([
        f"{instrument_type_emoji(pos.instrument_type)} <b>{pos.ticker}</b> — {pos.name}",
        _SEP,
        f"📌 <b>Тип:</b> {pos.instrument_type}",
        f"🏦 <b>Брокер:</b> {pos.broker_id}",
        f"💱 <b>Валюта:</b> {pos.currency}",
        _SEP,
        f"📦 <b>Количество:</b> {fmt_float(pos.quantity)} шт. ({fmt_float(pos.quantity_lots)} лотов)",
        f"📥 <b>Средняя цена входа:</b> {fmt_money(pos.average_price, pos.currency, 4)}",
        f"📊 <b>Текущая цена:</b> {fmt_money(pos.current_price, pos.currency, 4)}",
        f"💰 <b>Стоимость позиции:</b> {fmt_money(pos.current_value, '₽')}",
        _SEP,
        f"{pnl_icon} <b>Нереализованный PnL:</b> {fmt_pnl(pos.unrealized_pnl)}",
        f"   <b>% изменение:</b> {fmt_pct(pos.unrealized_pnl_pct)}",
    ])


def build_orders(orders: list[BrokerOrder], filter_label: str) -> str:
    lines = [
        f"📑 <b>Заявки</b> — {filter_label}",
        _SEP,
    ]

    if not orders:
        lines.append("🗂 <i>Заявок нет</i>")
        return "\n".join(lines)

    for o in orders:
        dir_icon = "🟢" if o.direction == OrderDirection.BUY else "🔴"
        status_label = {
            OrderStatus.NEW: "Новая",
            OrderStatus.PARTIALLY_FILLED: "Частично",
            OrderStatus.FILLED: "Исполнена",
            OrderStatus.CANCELLED: "Отменена",
            OrderStatus.REJECTED: "Отклонена",
            OrderStatus.EXPIRED: "Истекла",
        }.get(o.status, o.status.value)

        price_str = fmt_money(o.price, o.currency) if o.price else "рыночная"
        lines += [
            f"\n{dir_icon} <b>{o.ticker}</b> {o.direction.value} {o.order_type.value}",
            f"  Статус: {status_label}",
            f"  Лотов: {o.quantity} | Исполнено: {o.filled_quantity}",
            f"  Цена: {price_str}",
            f"  Создана: {fmt_datetime(o.created_at)}",
            f"  ID: <code>{o.order_id[:16]}…</code>",
        ]

    return "\n".join(lines)


def build_operations(operations: list[BrokerOperation], page: int = 0, per_page: int = 10) -> str:
    lines = [
        f"📜 <b>Операции</b> ({len(operations)} шт.)",
        _SEP,
    ]

    if not operations:
        lines.append("🗂 <i>Операций нет</i>")
        return "\n".join(lines)

    start = page * per_page
    page_items = operations[start: start + per_page]

    for op in page_items:
        icon = operation_type_emoji(op.operation_type.value)
        payment_str = fmt_pnl(op.payment, op.currency)
        ticker_part = f" {op.ticker}" if op.ticker else ""
        lines.append(
            f"{icon} <b>{op.operation_type.value}{ticker_part}</b> "
            f"— {payment_str} "
            f"<i>{fmt_datetime(op.executed_at)}</i>"
        )

    return "\n".join(lines)


def build_balance(balances: list[BrokerBalance]) -> str:
    if not balances:
        return "💰 <b>Баланс</b>\n" + _SEP + "\n🗂 <i>Нет данных о балансе</i>"

    lines = ["💰 <b>Баланс</b>", _SEP]
    for b in balances:
        lines += [
            f"💱 <b>{b.currency.upper()}</b>",
            f"  Доступно: {fmt_money(b.available, b.currency)}",
        ]
        if b.blocked > 0:
            lines.append(f"  Заблокировано: {fmt_money(b.blocked, b.currency)}")
            lines.append(f"  Итого: {fmt_money(b.total, b.currency)}")

    return "\n".join(lines)


def build_statistics(stats: FullStatistics) -> str:
    if not stats.has_data:
        return (
            "📈 <b>Статистика</b>\n"
            + _SEP + "\n"
            "🗂 <i>Недостаточно данных для анализа</i>\n\n"
            "Статистика появится после совершения\n"
            "первых закрытых сделок."
        )

    lines = [
        "📈 <b>Статистика торговли</b>",
        _SEP,
        "📅 <b>Доходность по периодам:</b>",
        f"  Сегодня:    {fmt_pnl(stats.pnl_today)}",
        f"  Вчера:      {fmt_pnl(stats.pnl_yesterday)}",
        f"  Неделя:     {fmt_pnl(stats.pnl_week)}",
        f"  Месяц:      {fmt_pnl(stats.pnl_month)}",
        f"  Квартал:    {fmt_pnl(stats.pnl_quarter)}",
        f"  Год:        {fmt_pnl(stats.pnl_year)}",
        f"  Всё время:  {fmt_pnl(stats.pnl_all_time)}",
        _SEP,
        "📊 <b>Показатели:</b>",
        f"  Сделок всего:   {stats.total_trades}",
        f"  Прибыльных:     {stats.winning_trades}",
        f"  Убыточных:      {stats.losing_trades}",
        f"  Win Rate:       {fmt_pct(stats.win_rate)}",
        f"  ROI:            {fmt_pct(stats.roi)}",
        _SEP,
        "⚡ <b>Качество торговли:</b>",
        f"  Ср. прибыль:    {fmt_money(stats.avg_profit)}",
        f"  Ср. убыток:     {fmt_money(stats.avg_loss)}",
        f"  Profit Factor:  {fmt_ratio(stats.profit_factor)}",
        f"  Recovery Factor:{fmt_ratio(stats.recovery_factor)}",
        f"  Max Drawdown:   {fmt_pct(stats.max_drawdown)}",
        f"  Sharpe Ratio:   {fmt_ratio(stats.sharpe_ratio)}",
        f"  Sortino Ratio:  {fmt_ratio(stats.sortino_ratio)}",
        _SEP,
        "🏆 <b>Экстремумы:</b>",
        f"  Лучший день:    {fmt_pnl(stats.best_day_pnl)} ({fmt_date(stats.best_day_date)})",
        f"  Худший день:    {fmt_pnl(stats.worst_day_pnl)} ({fmt_date(stats.worst_day_date)})",
        f"  Макс. прибыль: {fmt_pnl(stats.max_single_win)}",
        f"  Макс. убыток:  {fmt_pnl(stats.max_single_loss)}",
        f"  Ср. время удержания: {fmt_ratio(stats.avg_hold_hours)} ч.",
    ]
    return "\n".join(lines)


def build_broker_info(infos: list[BrokerInfo]) -> str:
    lines = ["🔗 <b>Подключённые брокеры</b>", _SEP]
    for info in infos:
        if info.is_connected:
            icon = "🟢"
            status = "Подключён"
        elif info.is_configured:
            icon = "🟡"
            status = "Настроен (нет соединения)"
        else:
            icon = "⚪"
            status = "Не настроен"
        lines += [
            f"\n{icon} <b>{info.name}</b>",
            f"  {info.description}",
            f"  Статус: {status}",
        ]
        if info.error:
            lines.append(f"  ⚠ {info.error}")
    return "\n".join(lines)


def build_trading_bot_status(summary: dict, logs: list[str]) -> str:
    status = summary.get("status", "STOPPED")
    icon = "🟢" if status == "RUNNING" else ("⏸" if status == "PAUSED" else "⏹")
    lines = [
        "🤖 <b>Торговый бот</b>",
        _SEP,
        f"{icon} <b>Статус:</b> {status}",
        f"🔄 <b>Циклов выполнено:</b> {summary.get('cycles_completed', 0)}",
        f"📊 <b>Сделок сегодня:</b> {summary.get('trades_today', 0)}",
        f"⚠ <b>Ошибок сегодня:</b> {summary.get('errors_today', 0)}",
    ]
    if summary.get("last_cycle_at"):
        lines.append(f"🕐 <b>Последний цикл:</b> {summary['last_cycle_at'][:16]}")
    if summary.get("started_at"):
        lines.append(f"▶ <b>Запущен:</b> {summary['started_at'][:16]}")
    if logs:
        lines += [_SEP, "📜 <b>Последние события:</b>"]
        lines += [f"  <code>{log}</code>" for log in logs[-10:]]
    return "\n".join(lines)
