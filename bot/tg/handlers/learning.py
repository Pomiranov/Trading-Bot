"""Learning system Telegram handlers — strategy confidence, hypotheses, decision quality."""
from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from tg.middlewares.auth import require_auth
from tg.middlewares.rate_limit import rate_limiter  # noqa: F401 — used inline

logger = logging.getLogger(__name__)


def _learning_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Стратегии",    callback_data="learn_strategies"),
            InlineKeyboardButton("🔬 Гипотезы",     callback_data="learn_hypotheses"),
        ],
        [
            InlineKeyboardButton("🧠 Решения",      callback_data="learn_decisions"),
            InlineKeyboardButton("🔄 Обновить",     callback_data="m_learning"),
        ],
        [InlineKeyboardButton("🏠 Главная",         callback_data="m_main")],
    ])


def _confidence_bar(value: float, width: int = 10) -> str:
    filled = round(value * width)
    return "█" * filled + "░" * (width - filled)


async def _render_learning_overview(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not await require_auth(update, context):
        if query:
            await query.answer()
        return
    if query:
        await query.answer()

    db_engine = context.bot_data.get("db_engine")
    if not db_engine:
        text = "⚠ <b>Learning</b>\n\nБД недоступна"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Главная", callback_data="m_main")]])
        _send_or_edit(update, query, text, kb)
        return

    try:
        from sqlalchemy import text as sql_text

        with db_engine.connect() as conn:
            # Strategy confidence summary
            strats = conn.execute(sql_text("""
                SELECT strategy_id, confidence, win_rate, total_trades
                FROM belief_system
                ORDER BY confidence DESC NULLS LAST
                LIMIT 5
            """)).fetchall()

            # Hypotheses counts by stage
            hyp_counts = conn.execute(sql_text("""
                SELECT stage, COUNT(*) AS cnt FROM hypotheses GROUP BY stage
            """)).fetchall()
            by_stage = {r[0]: int(r[1]) for r in hyp_counts}

            # Decision quality
            q_row = conn.execute(sql_text("""
                SELECT AVG(decision_quality) AS avg_q, COUNT(*) AS n
                FROM trades WHERE decision_quality IS NOT NULL
            """)).fetchone()
            avg_quality = round(float(q_row[0] or 0), 2) if q_row else 0.0
            quality_count = int(q_row[1] or 0) if q_row else 0

        # Learning active?
        learning_active = False
        try:
            from engine.paper_engine import paper_engine
            learning_active = paper_engine.status().get("learning_active", False)
        except Exception:
            pass

        status_icon = "🟢" if learning_active else "🔴"
        lines = [
            f"🧠 <b>Learning System</b>  {status_icon}",
            "",
            "<b>Стратегии:</b>",
        ]
        for s in strats:
            conf = float(s[1] or 0)
            wr = float(s[2] or 0) * 100
            n = int(s[3] or 0)
            bar = _confidence_bar(conf)
            lines.append(f"  <code>{s[0][:18]:<18}</code> {bar} {conf:.2f}  WR {wr:.0f}%  ({n})")

        total_hyp = sum(by_stage.values())
        lines += [
            "",
            "<b>Гипотезы:</b>",
            f"  🟢 Active: {by_stage.get('active', 0)}   "
            f"🔵 Candidate: {by_stage.get('candidate', 0)}   "
            f"👁 Obs: {by_stage.get('observation', 0)}   "
            f"❌ Rejected: {by_stage.get('rejected', 0)}",
            f"  Всего: {total_hyp}",
            "",
            f"<b>Качество решений:</b> {avg_quality:.2f} / 1.0  ({quality_count} оценено)",
        ]

        text = "\n".join(lines)
    except Exception as exc:
        logger.warning("learning overview tg error: %s", exc)
        text = f"⚠ <b>Learning</b>\n\nОшибка: {exc}"

    await _send_or_edit(update, query, text, _learning_keyboard())


async def _render_strategies(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not await require_auth(update, context):
        if query:
            await query.answer()
        return
    if query:
        await query.answer()

    db_engine = context.bot_data.get("db_engine")
    if not db_engine:
        await _send_or_edit(update, query, "⚠ БД недоступна", _back_kb())
        return

    try:
        from sqlalchemy import text as sql_text
        with db_engine.connect() as conn:
            rows = conn.execute(sql_text("""
                SELECT strategy_id, confidence, win_rate, total_trades,
                       profit_factor, expectancy, best_regime
                FROM belief_system ORDER BY confidence DESC NULLS LAST
            """)).fetchall()

        lines = ["📊 <b>Стратегии (belief_system)</b>", ""]
        for r in rows:
            conf = float(r[1] or 0)
            wr = float(r[2] or 0) * 100
            n = int(r[3] or 0)
            pf = float(r[4] or 0)
            exp = float(r[5] or 0)
            regime = r[6] or "—"
            bar = _confidence_bar(conf)
            lines += [
                f"<b>{r[0]}</b>",
                f"  Confidence: {bar} {conf:.3f}",
                f"  WR: {wr:.1f}%  PF: {pf:.2f}  Exp: {exp:.2f}  Сделок: {n}",
                f"  Режим: {regime}",
                "",
            ]
        text = "\n".join(lines) if len(lines) > 2 else "📊 Нет данных по стратегиям"
    except Exception as exc:
        text = f"⚠ Ошибка: {exc}"

    await _send_or_edit(update, query, text, _back_kb())


async def _render_hypotheses(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not await require_auth(update, context):
        if query:
            await query.answer()
        return
    if query:
        await query.answer()

    db_engine = context.bot_data.get("db_engine")
    if not db_engine:
        await _send_or_edit(update, query, "⚠ БД недоступна", _back_kb())
        return

    try:
        from sqlalchemy import text as sql_text
        with db_engine.connect() as conn:
            rows = conn.execute(sql_text("""
                SELECT description, stage, win_rate, total_trades, profit_factor
                FROM hypotheses
                WHERE stage IN ('active','candidate')
                ORDER BY stage, win_rate DESC NULLS LAST
                LIMIT 15
            """)).fetchall()

        STAGE_ICON = {"active": "🟢", "candidate": "🔵", "observation": "👁", "rejected": "❌"}
        lines = ["🔬 <b>Активные гипотезы</b>", ""]
        for r in rows:
            icon = STAGE_ICON.get(r[1], "•")
            wr = f"{float(r[2]) * 100:.1f}%" if r[2] else "—"
            n = int(r[3] or 0)
            pf = f"{float(r[4]):.2f}" if r[4] else "—"
            desc = r[0][:50]
            lines.append(f"{icon} {desc}")
            lines.append(f"   WR {wr}  PF {pf}  n={n}")
        text = "\n".join(lines) if len(lines) > 2 else "🔬 Нет активных/кандидатных гипотез"
    except Exception as exc:
        text = f"⚠ Ошибка: {exc}"

    await _send_or_edit(update, query, text, _back_kb())


async def _render_decisions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not await require_auth(update, context):
        if query:
            await query.answer()
        return
    if query:
        await query.answer()

    db_engine = context.bot_data.get("db_engine")
    if not db_engine:
        await _send_or_edit(update, query, "⚠ БД недоступна", _back_kb())
        return

    try:
        from sqlalchemy import text as sql_text
        with db_engine.connect() as conn:
            rows = conn.execute(sql_text("""
                SELECT ticker, strategy_id, decision_quality, pnl, closed_at
                FROM trades
                WHERE decision_quality IS NOT NULL AND closed_at IS NOT NULL
                ORDER BY closed_at DESC
                LIMIT 10
            """)).fetchall()

        lines = ["🧠 <b>Последние решения</b>", ""]
        for r in rows:
            q = float(r[2] or 0)
            pnl = float(r[3] or 0)
            pnl_icon = "📈" if pnl >= 0 else "📉"
            bar = _confidence_bar(q, width=8)
            ts = str(r[4])[:16] if r[4] else "—"
            lines.append(
                f"{pnl_icon} <b>{r[0]}</b> [{r[1] or '—'}]  Q={q:.2f} {bar}"
                f"\n   PnL: {pnl:+.2f}₽  {ts}"
            )
        text = "\n".join(lines) if len(lines) > 2 else "🧠 Нет оценённых решений"
    except Exception as exc:
        text = f"⚠ Ошибка: {exc}"

    await _send_or_edit(update, query, text, _back_kb())


def _back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("◀ Назад", callback_data="m_learning"),
            InlineKeyboardButton("🏠 Главная", callback_data="m_main"),
        ]
    ])


async def _send_or_edit(update, query, text: str, kb: InlineKeyboardMarkup) -> None:
    if query:
        try:
            await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            await query.message.reply_text(text, reply_markup=kb, parse_mode="HTML")
    elif update.message:
        await update.message.reply_text(text, reply_markup=kb, parse_mode="HTML")


# ── Public command + callback handlers ────────────────────────────────────────

async def cmd_learning(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user and not rate_limiter.is_allowed(update.effective_user.id):
        return
    await _render_learning_overview(update, context)


async def cb_learning_overview(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _render_learning_overview(update, context)


async def cb_learning_strategies(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _render_strategies(update, context)


async def cb_learning_hypotheses(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _render_hypotheses(update, context)


async def cb_learning_decisions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _render_decisions(update, context)
