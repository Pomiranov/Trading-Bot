# QuantFlow — Алгоритмический торговый бот для MOEX

<div align="center">

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.1+-000000?style=flat-square&logo=flask&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-TimescaleDB-4169E1?style=flat-square&logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker&logoColor=white)
![Tinkoff](https://img.shields.io/badge/Tinkoff-Invest%20API%20v2-FFDD2D?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-26a69a?style=flat-square)

**Торговый бот для Московской биржи с веб-дашбордом, сигнальным движком на технических индикаторах, управлением риском и интеграцией с Tinkoff Invest API.**

[Архитектура](#архитектура) · [Быстрый старт](#быстрый-старт) · [Dashboard](#web-dashboard) · [Сигналы](#сигнальный-движок) · [Бэктест](#бэктест) · [API](#rest-api) · [Конфигурация](#конфигурация) · [Безопасность](#безопасность)

</div>

---

## Содержание

- [Обзор](#обзор)
- [Возможности](#возможности)
- [Архитектура](#архитектура)
- [Стек технологий](#стек-технологий)
- [Структура проекта](#структура-проекта)
- [Быстрый старт](#быстрый-старт)
  - [Docker (рекомендуется)](#docker-рекомендуется)
  - [Python-окружение](#python-окружение)
  - [Загрузка исторических данных](#загрузка-исторических-данных)
- [Конфигурация](#конфигурация)
- [Web Dashboard](#web-dashboard)
- [Сигнальный движок](#сигнальный-движок)
- [Риск-менеджмент](#риск-менеджмент)
- [Брокер Tinkoff Invest](#брокер-tinkoff-invest)
- [Бэктест](#бэктест)
- [Telegram-бот](#telegram-бот)
- [REST API](#rest-api)
- [База данных](#база-данных)
- [Безопасность](#безопасность)
- [Roadmap](#roadmap)
- [Changelog](#changelog)
- [Дисклеймер](#дисклеймер)

---

## Обзор

QuantFlow — это production-ready алгоритмический торговый бот для **Московской биржи (MOEX)**. Система анализирует рыночные данные через технические индикаторы, генерирует торговые сигналы по YAML-правилам, управляет риском через ATR-стоп, исполняет сделки через **Tinkoff Invest API v2** и визуализирует всё через стеклянный веб-дашборд.

```
MOEX ISS API → Загрузка свечей → Технические индикаторы → Движок правил
     ↓                                                           ↓
TimescaleDB ←── Запись сделок ←── Риск-менеджмент ←── Сигнал BUY/SELL/HOLD
     ↓                                    ↓
Web Dashboard              Tinkoff Invest API v2
     ↓                                    ↓
Chart.js + SPA            Рыночный / Лимитный ордер
```

---

## Возможности

| Категория | Детали |
|---|---|
| **Рыночные данные** | MOEX ISS REST API: интервалы 1m / 5m / 10m / 15m / 30m / 1h / 1d / 1w |
| **Индикаторы** | RSI · MACD · EMA · ATR · Bollinger Bands · ADX+DI · VWAP |
| **Сигналы** | 12 правил на BUY / SELL из `knowledge/rules.yaml`, горячая перезагрузка |
| **Риск** | ATR-стоп · Размер позиции % от капитала · Дневной лимит убытков · Трейлинг-стоп |
| **Брокер** | Tinkoff Invest API v2 · Sandbox + Production · Рыночные и лимитные ордера |
| **Dashboard** | Flask SPA · 5 страниц · Chart.js · Glassmorphism UI · авто-обновление 30 сек |
| **Бэктест** | Событийный бэктестер · Комиссия 0.03% · Equity curve · Sharpe · Drawdown |
| **Telegram** | 7 команд: /status /signal /trades /stats /rules /stop /start |
| **БД** | PostgreSQL TimescaleDB · Лог сделок с контекстом сигнала · Статистика правил |

---

## Архитектура

```
┌──────────────────────────────────────────────────────────────────────┐
│                         MOEX ISS REST API                            │
│              https://iss.moex.com/iss — TQBR, дневные/часовые свечи │
└─────────────────────────────┬────────────────────────────────────────┘
                              │
                    data/loader.py
                    MoexLoader.get_candles()
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│                   СИГНАЛЬНЫЙ ДВИЖОК                                   │
│                                                                      │
│  signals/indicators.py          signals/rules_engine.py              │
│  IndicatorEngine                RulesEngine ← knowledge/rules.yaml   │
│  RSI · MACD · EMA · ATR         12 правил YAML · весовой скоринг     │
│  BB · ADX+DI · VWAP             BUY / SELL / HOLD + score            │
└─────────────────────────────┬────────────────────────────────────────┘
                              │ SignalResult
                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    РИСК-МЕНЕДЖМЕНТ                                    │
│                  risk/risk_manager.py                                │
│  ATR-стоп · Размер позиции · Лимит позиций · Дневной убыток         │
│  check_trade_allowed() · trailing_stop() · calculate_position()      │
└─────────────────────────────┬────────────────────────────────────────┘
                              │ RiskCheckResult.allowed
                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    БРОКЕР — TINKOFF INVEST API v2                    │
│              broker/tinkoff_client.py  (торговый цикл)              │
│              services/tinkoff/         (дашборд / портфель)         │
│  place_market_order · place_limit_order · cancel_order              │
│  get_portfolio · get_balance · find_instrument                      │
│  Sandbox / Production — переключение через .env                     │
└──────────────────────────────┬───────────────────────────────────────┘
              записывает       │              читает
              ▼                ▼                 ▼
┌────────────────────────────────────────────────────────────────────┐
│                   TimescaleDB (PostgreSQL)                          │
│  trades  — лог сделок, PnL, RSI/MACD/ADX в момент сигнала         │
│  candles — OHLCV исторические данные                               │
│  news    — лог событий (опционально)                               │
└────────────────────────────────┬───────────────────────────────────┘
                                 │
                                 ▼
┌────────────────────────────────────────────────────────────────────┐
│               WEB DASHBOARD  (ui/dashboard.py)                     │
│                   Flask · REST API · SPA                           │
│                                                                    │
│  📊 Dashboard  — метрики, equity curve, позиции, лог              │
│  📈 Portfolio  — котировки тикеров, дневные свечи                  │
│  ⚡ Signals   — live RSI · MACD · ADX · BB · сигнал               │
│  🔄 Backtest  — запуск и результаты бэктеста                       │
│  ⚙️  Settings  — конфигурация, Tinkoff-токены                      │
└────────────────────────────────┬───────────────────────────────────┘
                                 │
              ┌──────────────────┤
              │                  │
              ▼                  ▼
        Chart.js SPA      Telegram Bot
        Glassmorphism     7 команд управления
        Dark Terminal     python-telegram-bot
```

---

## Стек технологий

| Слой | Технология | Версия |
|---|---|---|
| Язык | Python | 3.11+ |
| Web-сервер | Flask | ≥ 3.1.0 |
| ORM / SQL | SQLAlchemy + psycopg2-binary | ≥ 2.0 |
| База данных | PostgreSQL + TimescaleDB | 15 |
| Брокер | tinkoff-investments SDK | ≥ 0.2.0b55 (тест на 0.2.0b59) |
| Рыночные данные | MOEX ISS REST API | — |
| Технические индикаторы | ta | ≥ 0.11.0 |
| Анализ данных | pandas | ≥ 2.0.0 |
| Конфигурация | python-dotenv | ≥ 1.0.0 |
| YAML-правила | PyYAML | ≥ 6.0 |
| HTTP-клиент | requests | ≥ 2.31.0 |
| Telegram | python-telegram-bot | ≥ 20.0 |
| Frontend | Vanilla JS · Chart.js 4 | — |
| Шрифты | Inter · JetBrains Mono | Google Fonts |
| Инфраструктура | Docker Compose | — |
| UI базы данных | Adminer | latest |

---

## Структура проекта

```
Trading-Bot-main/
│
├── main.py                      # Точка входа: торговый цикл + Telegram-бот
├── config.py                    # AppConfig, TinkoffConfig, RiskConfig через .env
├── requirements.txt             # Python-зависимости
├── docker-compose.yml           # TimescaleDB (pg15) + Adminer на :8080
├── .env.example                 # Шаблон переменных окружения
│
├── knowledge/
│   └── rules.yaml               # 12 торговых правил YAML (BUY/SELL + веса)
│
├── data/
│   └── loader.py                # MoexLoader: OHLCV с MOEX ISS, сохранение в БД
│
├── signals/
│   ├── indicators.py            # IndicatorEngine: RSI·MACD·EMA·ATR·BB·ADX·VWAP
│   └── rules_engine.py          # RulesEngine: оценка правил → SignalResult
│
├── risk/
│   └── risk_manager.py          # RiskManager: позиция, стоп, дневной PnL, трейлинг
│
├── broker/
│   └── tinkoff_client.py        # TinkoffClient: рыночные/лимитные ордера
│
├── backtest/
│   └── engine.py                # BacktestEngine: событийный, комиссия, equity curve
│
├── learning/
│   └── feedback.py              # FeedbackStore: запись/чтение сделок в PostgreSQL
│
├── services/
│   └── tinkoff/
│       ├── __init__.py          # Публичный API сервисного слоя
│       ├── client.py            # build_client(): Sandbox/Production + иерархия ошибок
│       ├── portfolio.py         # get_portfolio_summary(): позиции + кэш 30 сек
│       ├── statistics.py        # compute_bot_stats(): Sharpe, Drawdown, Win Rate
│       ├── cache.py             # TTLCache: in-memory кэш с истечением
│       ├── mapper.py            # Quotation → float, MoneyValue → float
│       └── types.py             # Position, PortfolioSummary, BotStatistics
│
└── ui/
    ├── dashboard.py             # Flask: 18 REST-маршрутов + рендер SPA
    ├── telegram_bot.py          # Telegram-бот: 7 команд
    ├── templates/
    │   └── dashboard.html       # SPA: 5 страниц, Chart.js, анимации, ripple
    └── static/
        └── style.css            # Glassmorphism dark terminal: CSS custom properties
```

---

## Быстрый старт

### Требования

- **Docker** 24+ и Docker Compose v2 — для запуска TimescaleDB
- **Python** 3.11+ — для бота и дашборда
- **Аккаунт Т-Инвестиции** — токен API (sandbox или production)

### Docker (рекомендуется)

Запустите TimescaleDB и Adminer одной командой:

```bash
git clone https://github.com/your-username/quantflow.git
cd quantflow

# Поднять БД
docker compose up -d

# Проверить статус
docker compose ps
```

После запуска:
- **TimescaleDB** доступна на `localhost:5432`
- **Adminer** (веб-интерфейс БД) на `http://localhost:8080`
  - Система: PostgreSQL, Сервер: `timescaledb`, Логин: `trader`, Пароль: значение `DB_PASSWORD` из `.env`, БД: `trading_bot`

### Python-окружение

```bash
# Создать виртуальное окружение
python3 -m venv .venv
source .venv/bin/activate       # Linux/macOS
# .venv\Scripts\activate        # Windows

# Установить зависимости
pip install -r requirements.txt

# Скопировать и заполнить .env
cp .env.example .env
nano .env                       # минимум: DB_PASSWORD, TINKOFF_TOKEN, TINKOFF_ACCOUNT_ID
```

### Создание схемы БД

Схема таблицы `trades` создаётся автоматически при первом запуске `main.py` или `ui/dashboard.py` через `learning/feedback.py`.

Для таблицы `candles` и `news` выполните вручную или через Adminer:

```sql
CREATE TABLE IF NOT EXISTS candles (
    time       TIMESTAMPTZ NOT NULL,
    ticker     VARCHAR(20) NOT NULL,
    timeframe  VARCHAR(10) NOT NULL,
    open       NUMERIC(18,4),
    high       NUMERIC(18,4),
    low        NUMERIC(18,4),
    close      NUMERIC(18,4),
    volume     BIGINT
);

-- Для TimescaleDB (рекомендуется):
SELECT create_hypertable('candles', 'time', if_not_exists => TRUE);

CREATE UNIQUE INDEX IF NOT EXISTS idx_candles_uniq
    ON candles (ticker, timeframe, time DESC);
```

### Загрузка исторических данных

`data/loader.py` запускается как скрипт — загружает OHLCV с MOEX ISS и сохраняет в таблицу `candles`:

```bash
# Загрузить дневные свечи за последний год (по умолчанию)
python3 data/loader.py

# Указать тикеры, интервал и период
python3 data/loader.py SBER GAZP LKOH NVTK --interval 1d --days 730

# Доступные интервалы
# 1m  5m  10m  15m  30m  1h  1d  1w  1M
```

### Запуск веб-дашборда

```bash
python3 ui/dashboard.py
# Дашборд доступен на http://localhost:5001
```

### Запуск торгового бота

```bash
# Полный режим: торговый цикл + Telegram-бот в отдельном потоке
python3 main.py

# Только Telegram-бот (без автоматической торговли)
python3 main.py --bot-only

# Только бэктест по тикерам из TICKERS
python3 main.py --backtest
```

> **Внимание:** перед live-торговлей убедитесь, что `TINKOFF_SANDBOX=true` в `.env`. Переключение на `false` исполняет сделки с реальными деньгами.

---

## Конфигурация

Скопируйте `.env.example` в `.env` и заполните значения:

```dotenv
# ─── База данных PostgreSQL / TimescaleDB ──────────────────────────────────
DB_HOST=localhost
DB_PORT=5432
DB_NAME=trading_bot
DB_USER=trader
DB_PASSWORD=your_password_here       # docker-compose подставляет его через ${DB_PASSWORD}

# ─── Т-Инвестиции API ──────────────────────────────────────────────────────
TINKOFF_TOKEN=your_tinkoff_token_here        # t.xxxxxxxxxxxxxxxx
TINKOFF_ACCOUNT_ID=your_account_id_here      # идентификатор счёта
TINKOFF_SANDBOX=true                          # true = песочница  false = боевой

# ─── Telegram ──────────────────────────────────────────────────────────────
TELEGRAM_TOKEN=your_telegram_bot_token_here  # от @BotFather
TELEGRAM_CHAT_ID=your_chat_id_here           # ваш Telegram user ID

# ─── Торгуемые инструменты ─────────────────────────────────────────────────
TICKERS=SBER,GAZP,LKOH,YNDX,NVTK            # через запятую, без пробелов
POLL_INTERVAL=60                              # секунд между итерациями цикла

# ─── Риск-менеджмент ───────────────────────────────────────────────────────
RISK_MAX_POSITION_PCT=0.05       # макс. % портфеля на одну позицию (5%)
RISK_ATR_STOP_MULT=2.0           # множитель ATR для расчёта стоп-лосса
RISK_MAX_DAILY_LOSS_PCT=0.02     # лимит дневных убытков (2% от портфеля)
RISK_MAX_OPEN_POSITIONS=5        # макс. одновременных позиций

# ─── Приложение ────────────────────────────────────────────────────────────
LOG_LEVEL=INFO                   # DEBUG / INFO / WARNING / ERROR
```

### Все параметры конфигурации

| Переменная | По умолчанию | Описание |
|---|---|---|
| `DB_HOST` | `localhost` | Хост PostgreSQL |
| `DB_PORT` | `5432` | Порт PostgreSQL |
| `DB_NAME` | `trading_bot` | Имя базы данных |
| `DB_USER` | `trader` | Пользователь БД |
| `DB_PASSWORD` | — | Пароль БД **(обязательно)** |
| `TINKOFF_TOKEN` | — | Токен API Т-Инвестиции **(обязательно)** |
| `TINKOFF_ACCOUNT_ID` | — | ID торгового счёта **(обязательно)** |
| `TINKOFF_SANDBOX` | `true` | Режим песочницы |
| `TELEGRAM_TOKEN` | — | Токен Telegram-бота (опционально) |
| `TELEGRAM_CHAT_ID` | — | ID чата для уведомлений (опционально) |
| `TICKERS` | `SBER,GAZP,LKOH,YNDX,NVTK` | Торгуемые тикеры |
| `POLL_INTERVAL` | `60` | Интервал опроса, сек |
| `RISK_MAX_POSITION_PCT` | `0.05` | Макс. доля капитала на позицию |
| `RISK_ATR_STOP_MULT` | `2.0` | Множитель ATR для стоп-лосса |
| `RISK_MAX_DAILY_LOSS_PCT` | `0.02` | Лимит дневного убытка |
| `RISK_MAX_OPEN_POSITIONS` | `5` | Макс. число позиций |
| `LOG_LEVEL` | `INFO` | Уровень логирования |

---

## Web Dashboard

Дашборд запускается командой `python3 ui/dashboard.py` и доступен на `http://localhost:5001`.

Это SPA (Single-Page Application) на ванильном JavaScript с пятью страницами:

### Dashboard

Главная страница с мониторингом в реальном времени. Обновляется автоматически каждые 30 секунд.

| Элемент | Данные |
|---|---|
| **Portfolio** | Стоимость портфеля из Tinkoff API + количество позиций |
| **Нереализованный P&L** | Unrealized PnL + % от стоимости входа |
| **Просадка / Win Rate** | Max Drawdown % + процент прибыльных сделок |
| **Sharpe Ratio** | Аннуализированный коэффициент (252 торговых дня) |
| **Equity Curve** | График капитала из истории закрытых сделок |
| **Последние сигналы** | Таблица: время, тикер, BUY/SELL/HOLD, цена, скор, правил |
| **Позиции Tinkoff** | Список позиций: тикер, P&L, средняя цена, текущая цена |
| **Риск-менеджмент** | Прогресс-бары: P&L, просадка, позиций, Win Rate |
| **Лог событий** | Последние записи из таблицы `news` |

Если Tinkoff API недоступен или токен не настроен — дашборд показывает плейсхолдеры (`—`, `Нет данных`), а не пустой экран.

### Portfolio

Котировки торгуемых тикеров из таблицы `candles`:

- Карточки тикеров: текущая цена, изменение за 1 день, изменение за 30 дней, объём
- Интерактивный график дневных свечей (Chart.js, закрытие)
- Переключение между тикерами через вкладки

### Signals

Live-вычисление технических индикаторов по последним данным из `candles`:

- Карточки по каждому тикеру: сигнал (BUY/SELL/HOLD), RSI с визуальной полосой, MACD гистограмма, ADX, score
- Подробная таблица: RSI, MACD, ADX, BB%, buy_score, sell_score, количество правил
- Блок сработавших правил

### Backtest

Запуск событийного бэктеста по всем тикерам из БД:

- Начальный капитал: 1 000 000 ₽, комиссия: 0.03% за сторону
- Таблица результатов: сделок, Win%, PnL, Avg PnL, Max Drawdown, Sharpe, свечей
- Сравнительный график equity curve по тикерам

### Settings

Просмотр конфигурации и управление токенами:

- **База данных** — хост, порт, имя, статус подключения
- **Риск-менеджмент** — все 4 параметра из `.env`
- **Приложение** — тикеры, интервал опроса, уровень логов
- **Брокер (Tinkoff)** — режим (Sandbox/Production), статус, Account ID
- Поля ввода токенов с переключателем показать/скрыть
- Сохранение токена записывает значение в `.env` и немедленно применяет без перезапуска

---

## Сигнальный движок

### Технические индикаторы

Библиотека: `ta` (Technical Analysis Library).

| Индикатор | Параметры | Назначение |
|---|---|---|
| **RSI** | period=14 | Индекс относительной силы |
| **MACD** | 12/26/9 | Схождение/расхождение скользящих средних |
| **EMA fast** | period=9 | Быстрая экспоненциальная MA |
| **EMA slow** | period=21 | Медленная экспоненциальная MA |
| **ATR** | period=14 | Истинный средний диапазон (волатильность) |
| **Bollinger Bands** | 20, σ=2.0 | Полосы волатильности + BB% |
| **ADX** | period=14 | Индикатор направленного движения |
| **+DI / -DI** | period=14 | Положительный / отрицательный тренд |
| **VWAP** | — | Средневзвешенная по объёму цена |

Вычисляемые состояния (`IndicatorValues`): `macd_bullish_cross`, `macd_bearish_cross`, `price_above_ema_fast`, `price_above_ema_slow`, `trend_strong`, `rsi_oversold`, `rsi_overbought`.

### Торговые правила (knowledge/rules.yaml)

Движок оценивает условия через `operator` (`>`, `<`, `>=`, `<=`, `==`). Значение может быть числом или ссылкой на другой индикатор (`value: adx_neg`).

**Правила BUY:**

| Правило | Вес | Условия |
|---|---|---|
| `RSI_Oversold_Bounce` | 1.0 | RSI < 35 AND MACD гист. > 0 |
| `EMA_Bullish_Cross` | 1.5 | Цена > EMA_fast AND > EMA_slow AND ADX > 20 |
| `MACD_Bullish_Crossover` | 1.2 | MACD бычий крест AND RSI ∈ (40, 65) |
| `BB_Lower_Bounce` | 0.8 | BB% < 0.1 AND RSI < 40 AND ADX < 30 |
| `Strong_Trend_Continuation_Buy` | 1.8 | ADX > 30 AND +DI > -DI AND Цена > EMA_fast |
| `VWAP_Support_Buy` | 0.7 | Цена > VWAP |

**Правила SELL:**

| Правило | Вес | Условия |
|---|---|---|
| `RSI_Overbought_Exit` | 1.0 | RSI > 70 AND MACD гист. < 0 |
| `EMA_Bearish_Cross` | 1.5 | Цена < EMA_fast AND < EMA_slow AND ADX > 20 |
| `MACD_Bearish_Crossover` | 1.2 | MACD медвежий крест AND RSI > 50 |
| `BB_Upper_Rejection` | 0.8 | BB% > 0.9 AND RSI > 60 |
| `Strong_Trend_Continuation_Sell` | 1.8 | ADX > 30 AND -DI > +DI AND Цена < EMA_fast |
| `VWAP_Resistance_Sell` | 0.7 | Цена < VWAP |

**Параметры агрегации:**

```yaml
settings:
  min_buy_score: 2.0        # минимальная сумма весов для BUY
  min_sell_score: 2.0       # минимальная сумма весов для SELL
  confirmation_rules: 2     # минимальное количество сработавших правил
```

### Горячая перезагрузка правил

```python
from signals.rules_engine import rules_engine
rules_engine.reload()   # перечитывает knowledge/rules.yaml без перезапуска
```

---

## Риск-менеджмент

### Расчёт размера позиции (ATR-метод)

```
stop_distance  = ATR × RISK_ATR_STOP_MULT
stop_price     = entry_price − stop_distance  (для лонга)
risk_per_share = |entry_price − stop_price|
max_risk_amount = portfolio_value × RISK_MAX_POSITION_PCT
shares         = max_risk_amount / risk_per_share
```

### Проверки перед сделкой (`check_trade_allowed`)

1. **Лимит позиций** — `len(open_positions) < RISK_MAX_OPEN_POSITIONS`
2. **Нет дублирующей позиции** — тикер не в `open_positions`
3. **Дневной лимит убытков** — `daily_pnl > -(portfolio_value × RISK_MAX_DAILY_LOSS_PCT)`
4. **Размер позиции** — `position_value ≤ portfolio_value`

### Трейлинг-стоп

На каждой свече `trailing_stop()` вычисляет новый стоп:

```
new_stop = current_price − ATR × RISK_ATR_STOP_MULT
if new_stop > position.stop_price:
    position.stop_price = new_stop
```

---

## Брокер Tinkoff Invest

### Архитектура клиента

В проекте два уровня клиентского кода:

- `broker/tinkoff_client.py` — используется **торговым циклом** (`main.py`) для исполнения ордеров
- `services/tinkoff/` — используется **дашбордом** (`ui/dashboard.py`) для отображения портфеля

### Получение токена

1. Откройте [Tinkoff Invest](https://www.tbank.ru/invest/)
2. Перейдите в Настройки → Интеграция → Создать токен
3. Скопируйте токен в `.env` → `TINKOFF_TOKEN`

Получение Account ID:
```python
from tinkoff.invest import Client
with Client("your_token") as c:
    for acc in c.users.get_accounts().accounts:
        print(acc.id, acc.name)
```

### Sandbox vs Production

```dotenv
TINKOFF_SANDBOX=true    # виртуальные деньги, безопасно
TINKOFF_SANDBOX=false   # реальные деньги — использовать осознанно
```

Sandbox использует тот же endpoint (`INVEST_GRPC_API_SANDBOX`) через стандартный `Client`. Для пополнения счёта в sandbox используйте личный кабинет Т-Инвестиций.

### TTL-кэш портфеля

| Данные | TTL |
|---|---|
| Портфель и позиции | 30 секунд |
| Инструменты (ticker ↔ FIGI) | 1 час |
| Статистика бота из БД | 5 минут |

Кэш сбрасывается автоматически при сохранении нового токена через Settings.

---

## Бэктест

### Принцип работы

Событийный бэктестер `backtest/engine.py` прогоняет стратегию свеча за свечой:

1. **Стоп-лосс** — проверяется перед сигналом на каждой свече
2. **Индикаторы** — вычисляются на окне последних 60 свечей
3. **Открытие** — при сигнале BUY и отсутствии позиции
4. **Закрытие** — при сигнале SELL или срабатывании стоп-лосса
5. **Трейлинг-стоп** — обновляется на каждой свече
6. **Принудительное закрытие** — на последней свече

**Параметры по умолчанию:**
- Начальный капитал: 1 000 000 ₽
- Комиссия: 0.03% (обе стороны, как у большинства брокеров)
- Минимум данных: 50 свечей
- Размер лота: 1

### Метрики результата

```python
BacktestResult:
    total_trades    # всего сделок
    winning_trades  # прибыльных
    losing_trades   # убыточных
    win_rate        # %  прибыльных
    total_pnl       # суммарный PnL в ₽
    avg_pnl         # средний PnL на сделку
    max_drawdown    # максимальная просадка %
    sharpe          # коэффициент Шарпа (rf = 16% годовых)
    equity_curve    # список значений капитала
```

### Запуск через CLI

```bash
# Быстрый бэктест из командной строки
python3 main.py --backtest

# Бэктест через дашборд (POST /api/backtest)
# Страница Backtest → кнопка "▶ Запустить бэктест"
```

---

## Telegram-бот

Бот запускается параллельно с торговым циклом в отдельном потоке.

| Команда | Описание |
|---|---|
| `/start` | Приветствие и список команд |
| `/status` | Статус цикла, дневной PnL, открытые позиции |
| `/signal <TICKER>` | Live-сигнал для тикера: RSI, MACD, ADX, ATR, сработавшие правила |
| `/trades` | Последние 10 сделок из БД |
| `/stats` | Суммарная статистика: Win Rate, PnL, лучшая/худшая сделка |
| `/rules` | Список загруженных правил с весами |
| `/stop` | Остановить торговый цикл |

Уведомления о сделках отправляются автоматически при каждой покупке и продаже:

```
🟢 ПОКУПКА SBER
Цена: 315.20 руб.
Лотов: 3 | Акций: 30
Стоп: 309.40 руб.
Счёт: 3.50
```

---

## REST API

Все эндпоинты дашборда на порту 5001.

### Tinkoff

| Метод | Путь | Описание |
|---|---|---|
| `GET` | `/api/tinkoff/portfolio` | Стоимость портфеля, количество позиций |
| `GET` | `/api/tinkoff/positions` | Список позиций с P&L, ценами, лотами |
| `GET` | `/api/tinkoff/pnl` | Нереализованный P&L + % |

Коды ошибок в теле ответа:

| `error_code` | HTTP | Причина |
|---|---|---|
| `NOT_CONFIGURED` | 503 | Не заданы `TINKOFF_TOKEN` или `TINKOFF_ACCOUNT_ID` |
| `SDK_ERROR` | 503 | Пакет `tinkoff-investments` не установлен |
| `API_ERROR` | 502 | Ошибка запроса к Tinkoff Invest API |

### Статистика и данные

| Метод | Путь | Описание |
|---|---|---|
| `GET` | `/api/stats` | Sharpe, Drawdown, Win Rate из БД (null если нет данных) |
| `GET` | `/api/equity` | Equity curve из закрытых сделок |
| `GET` | `/api/signals` | Последние 50 сигналов из таблицы `trades` |
| `GET` | `/api/signals/live` | Live-вычисление индикаторов по тикерам из `candles` |
| `GET` | `/api/portfolio` | Сводка котировок тикеров: цена, 1d/30d change, объём |
| `GET` | `/api/candles?ticker=SBER&limit=120` | OHLCV свечи тикера (дневные) |
| `GET` | `/api/metrics` | Агрегированные метрики из таблицы `trades` |
| `GET` | `/api/positions` | Открытые позиции из таблицы `trades` |
| `GET` | `/api/log` | Последние события из таблицы `news` |

### Настройки

| Метод | Путь | Описание |
|---|---|---|
| `GET` | `/api/settings` | Конфигурация: DB, Risk, App, Tinkoff (без значений токенов) |
| `GET` | `/api/settings/tokens` | `{has_tinkoff_token: bool, has_tinkoff_account_id: bool}` |
| `POST` | `/api/settings/tokens` | Сохранить токен: `{"key": "TINKOFF_TOKEN", "value": "t.xxx"}` |

### Бэктест

| Метод | Путь | Описание |
|---|---|---|
| `POST` | `/api/backtest` | Запустить бэктест, вернуть результаты по всем тикерам |

### Примеры запросов

```bash
# Портфель
curl http://localhost:5001/api/tinkoff/portfolio

# Статус токенов (безопасно — без значений)
curl http://localhost:5001/api/settings/tokens

# Сохранить токен
curl -X POST http://localhost:5001/api/settings/tokens \
  -H "Content-Type: application/json" \
  -d '{"key": "TINKOFF_TOKEN", "value": "t.your_token_here"}'

# Live-сигналы
curl http://localhost:5001/api/signals/live

# Свечи SBER за 90 дней
curl "http://localhost:5001/api/candles?ticker=SBER&limit=90"

# Запуск бэктеста
curl -X POST http://localhost:5001/api/backtest
```

---

## База данных

### Таблица `trades` — лог сделок

```sql
CREATE TABLE trades (
    id              SERIAL PRIMARY KEY,
    ticker          VARCHAR(20)   NOT NULL,
    direction       VARCHAR(4)    NOT NULL,   -- BUY / SELL
    entry_price     NUMERIC(18,4) NOT NULL,
    exit_price      NUMERIC(18,4),
    shares          INTEGER       NOT NULL,
    stop_price      NUMERIC(18,4),
    pnl             NUMERIC(18,4),
    pnl_pct         NUMERIC(10,6),
    entry_at        TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    exit_at         TIMESTAMPTZ,
    signal_rules    TEXT[],                   -- список сработавших правил
    buy_score       NUMERIC(8,4),
    sell_score      NUMERIC(8,4),
    rsi             NUMERIC(8,4),             -- RSI в момент сигнала
    macd_hist       NUMERIC(18,6),
    adx             NUMERIC(8,4),
    atr             NUMERIC(18,6),
    status          VARCHAR(20) DEFAULT 'OPEN',  -- OPEN / CLOSED / STOPPED
    notes           TEXT
);
```

### Таблица `candles` — OHLCV-данные

```sql
CREATE TABLE candles (
    time       TIMESTAMPTZ NOT NULL,
    ticker     VARCHAR(20) NOT NULL,
    timeframe  VARCHAR(10) NOT NULL,   -- '1d', '1h', '1m', ...
    open       NUMERIC(18,4),
    high       NUMERIC(18,4),
    low        NUMERIC(18,4),
    close      NUMERIC(18,4),
    volume     BIGINT
);
-- TimescaleDB hypertable по полю time
```

### Анализ эффективности правил

`FeedbackStore.get_rule_performance()` возвращает статистику по каждому правилу:

```sql
SELECT rule,
       COUNT(*)                         AS total,
       COUNT(*) FILTER (WHERE pnl > 0)  AS wins,
       ROUND(SUM(pnl)::numeric, 2)      AS total_pnl
FROM trades, UNNEST(signal_rules) AS rule
WHERE status IN ('CLOSED', 'STOPPED')
GROUP BY rule
ORDER BY total_pnl DESC;
```

---

## Безопасность

> **Токены API никогда не попадают в логи, ответы API или фронтенд.**

### Хранение токенов

- Токены хранятся **только в `.env`** — файл исключён из Git через `.gitignore`
- `_save_env_key()` использует `python-dotenv set_key()` для записи в `.env`
- При сохранении через UI значение применяется в `config.tinkoff.token` без перезапуска

### Защита API

```python
# Белый список допустимых ключей — других принять невозможно
_ALLOWED_TOKEN_KEYS = {"TINKOFF_TOKEN", "TINKOFF_ACCOUNT_ID"}

# GET /api/settings/tokens — возвращает ТОЛЬКО флаги присутствия
{"has_tinkoff_token": true, "has_tinkoff_account_id": false}

# POST: ключ логируется, значение — НИКОГДА
logger.info("Credential updated: key=%s", key)   # value не передаётся в logger
```

### Защита фронтенда

- Поля токенов: `type="password"` по умолчанию
- Кнопка «глаз» переключает `input.type` только на клиенте
- При потере фокуса (`input.blur`) поле возвращается в режим `password`

### Проверьте перед запуском

```bash
# Убедиться что .env в .gitignore
cat .gitignore | grep .env

# Убедиться что .env не в git
git status .env
# должно быть: nothing to commit
```

---

## Roadmap

| Версия | Статус | Задачи |
|---|---|---|
| **v0.1** | ✅ Готово | Торговый цикл · MOEX загрузка · YAML-правила · Tinkoff API · Flask Dashboard |
| **v0.2** | ✅ Готово | Glassmorphism UI · Бэктест в дашборде · Live-сигналы · TTL-кэш |
| **v0.3** | 🔄 В работе | Исправление схемы БД (status → closed_at) · Шарп в статистике |
| **v0.4** | ⏳ Запланировано | Рыночные часы MOEX · Авто-перезапуск · Healthcheck endpoint |
| **v0.5** | ⏳ Запланировано | WebSocket для live-котировок · Push-уведомления в дашборд |
| **v1.0** | ⏳ Запланировано | ML-сигналы (LightGBM на features из индикаторов) · A/B тест правил |

### Ближайшие задачи

- [ ] Унифицировать поле статуса в `trades`: использовать `closed_at IS NOT NULL` вместо `status IN ('CLOSED', 'STOPPED')`
- [ ] Добавить endpoint `/health` для мониторинга
- [ ] Написать SQL-миграции вместо ручного DDL
- [ ] Добавить поддержку мультивалютных портфелей (USD, EUR)
- [ ] Параметризовать правила из UI без редактирования YAML

---

## Changelog

### 2026-06-27 — v0.2.0

- **Dashboard**: полный рефакторинг SPA — glassmorphism, курсорное свечение, ripple-эффект, анимации, AbortController + дедупликация запросов
- **Settings**: кредиты Tinkoff перенесены внутрь карточки "Брокер (Tinkoff)", убрана отдельная секция
- **Dashboard**: гарантированный вывод данных при недоступном API — плейсхолдеры вместо пустого экрана
- **CSS**: полный редизайн — CSS custom properties, `backdrop-filter: blur(22px)`, gradient body, spring easing
- **Topbar**: часы, кнопка обновления, индикатор статуса API
- **P&L/Sharpe/Drawdown**: корректная обработка `null` из БД при нулевом количестве сделок

### 2026-06-26 — v0.1.0

- **Tinkoff SDK**: замена `SandboxClient` на `Client(token, target=INVEST_GRPC_API_SANDBOX)` — совместимость с 0.2.0b59
- **services/tinkoff**: выделен отдельный слой — `portfolio.py`, `statistics.py`, `cache.py`, `mapper.py`, `types.py`
- **Backtester**: события в UI, equity curves через Chart.js, таблица результатов
- **requirements.txt**: раскомментирован `tinkoff-investments`

### 2026-06-26 — v0.0.1 (Initial commit)

- Базовая структура: `main.py`, `config.py`, `data/loader.py`, `signals/`, `risk/`, `broker/`
- `knowledge/rules.yaml`: 12 торговых правил
- Flask Dashboard: первичный вариант с 5 страницами
- Docker Compose: TimescaleDB + Adminer
- Telegram-бот: 7 команд

---

## Дисклеймер

> Данный проект предназначен исключительно для **образовательных и исследовательских целей**.
>
> Алгоритмическая торговля сопряжена с существенными финансовыми рисками. Прошлые результаты бэктестов на исторических данных не гарантируют и не предсказывают будущую доходность.
>
> **Перед использованием в реальной торговле** всегда тестируйте в Sandbox (`TINKOFF_SANDBOX=true`) и консультируйтесь с лицензированным финансовым советником.
>
> Авторы не несут ответственности за финансовые потери, возникшие в результате использования данного программного обеспечения.

---

<div align="center">

Сделано для MOEX · Tinkoff Invest API v2 · Flask · TimescaleDB

</div>
