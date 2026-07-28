"""Засев belief-строки производной стратегии — ОДНО место (долг №30).

Было две копии одной логики: `run_forward_d1.py::_seed_belief` и
`main.py::_seed_belief`. Обе копировали `confidence` из исходной стратегии, и
форвард из-за этого получил 0.6574 при НУЛЕ собственных сделок — доверие без
свидетельств. У `main.py` тот же приём был заряжен на 0.2887 (§5а PROJECT_STATE):
значение не описывает ни EMA50, ни то, что исполнится, а порог 0.20 проходит.

ПРАВИЛО: наследуются только ОПИСАТЕЛЬНЫЕ поля (`strategy_name`, `market`,
`description`). `confidence`, `best_regime`, `best_timeframe` НЕ наследуются —
все три суть выводы из измерений исходной стратегии, а измерения относятся к её
набору правил, не к новому. `confidence` берётся из дефолта схемы (0.5).

Наследование доверия разрешается ТОЛЬКО при совпадении `rules_version` источника
и цели (требование, восстановленное в docs/ML_ROADMAP.md, этап 2.5). Пока у
источников отпечатков нет, условие невыполнимо по построению, то есть сегодня оно
эквивалентно «не наследовать» — и реализовано именно так, а не проверкой, которая
незаметно начнёт пропускать.
"""

import logging

logger = logging.getLogger(__name__)


async def seed_belief(
    conn,
    *,
    strategy_id: str,
    seed_from: str,
    name_suffix: str,
    fallback_name: str,
    fallback_description: str,
    fallback_market: str = "stocks",
) -> bool:
    """Создать belief-строку, если её нет. True — создали, False — уже была.

    conn — asyncpg-соединение (оба вызывающих дают именно его).
    Идемпотентно: повторный вызов ничего не меняет.
    """
    if await conn.fetchval(
        "SELECT 1 FROM belief_system WHERE strategy_id = $1", strategy_id
    ):
        return False

    # confidence / best_regime / best_timeframe СОЗНАТЕЛЬНО не в списке колонок:
    # они пришли бы из измерений ЧУЖОГО набора правил. confidence возьмётся из
    # DEFAULT 0.5 схемы.
    await conn.execute("""
        INSERT INTO belief_system (strategy_id, strategy_name, market, description)
        SELECT $1, strategy_name || $3, market, description
        FROM belief_system WHERE strategy_id = $2
        ON CONFLICT (strategy_id) DO NOTHING
    """, strategy_id, seed_from, name_suffix)

    if not await conn.fetchval(
        "SELECT 1 FROM belief_system WHERE strategy_id = $1", strategy_id
    ):   # источника нет — минимальная строка с дефолтами
        await conn.execute("""
            INSERT INTO belief_system (strategy_id, strategy_name, market, description)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (strategy_id) DO NOTHING
        """, strategy_id, fallback_name, fallback_market, fallback_description)

    logger.info("Belief-строка %s создана (confidence не наследован)", strategy_id)
    return True
