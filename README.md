# QuantFlow — Professional AI-Powered Investment & Trading Platform

<div align="center">

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111+-009688?style=flat-square&logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-4169E1?style=flat-square&logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-7.2+-DC382D?style=flat-square&logo=redis&logoColor=white)
![Kafka](https://img.shields.io/badge/Kafka-3.7+-231F20?style=flat-square&logo=apachekafka&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)
![Build](https://img.shields.io/badge/Build-Passing-brightgreen?style=flat-square)
![Coverage](https://img.shields.io/badge/Coverage-87%25-green?style=flat-square)

**Профессиональная микросервисная платформа для автоматической торговли акциями, ETF, облигациями и фьючерсами с гибридным AI-движком, управлением риском и оптимизацией портфеля.**

[Архитектура](#архитектура) · [Быстрый старт](#быстрый-старт) · [Модули](#модули) · [AI Engine](#ai-prediction-engine) · [Risk Engine](#risk-engine) · [API Docs](#api-документация) · [Деплой](#деплой) · [Contributing](#contributing)

</div>

---

## Содержание

- [Обзор системы](#обзор-системы)
- [Архитектура](#архитектура)
- [Стек технологий](#стек-технологий)
- [Структура репозитория](#структура-репозитория)
- [Модули](#модули)
  - [Market Data Service](#market-data-service)
  - [News Intelligence Service](#news-intelligence-service)
  - [Macroeconomic Service](#macroeconomic-service)
  - [Political Risk Service](#political-risk-service)
  - [Social Sentiment Service](#social-sentiment-service)
  - [Fundamental Analysis Service](#fundamental-analysis-service)
  - [Technical Analysis Service](#technical-analysis-service)
  - [AI Prediction Engine](#ai-prediction-engine)
  - [Portfolio Optimizer](#portfolio-optimizer)
  - [Risk Engine](#risk-engine)
  - [Execution Engine](#execution-engine)
  - [Monitoring Service](#monitoring-service)
- [Быстрый старт](#быстрый-старт)
- [Конфигурация](#конфигурация)
- [API Документация](#api-документация)
- [Тестирование](#тестирование)
- [Деплой](#деплой)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [Лицензия](#лицензия)

---

## Обзор системы

QuantFlow — это production-ready платформа для алгоритмической торговли, построенная по принципам **Clean Architecture**, **Domain Driven Design** и **Event-Driven Architecture**. Система способна:

- собирать и нормализовывать рыночные, новостные, макроэкономические и альтернативные данные в реальном времени;
- анализировать фундаментальные, технические, политические и сентиментальные факторы;
- генерировать торговые сигналы через гибридный ансамбль моделей (XGBoost + LightGBM + CatBoost + LSTM + Transformer);
- формировать и оптимизировать портфель методами MPT, Black-Litterman и Risk Parity;
- управлять риском через VaR, Expected Shortfall, Drawdown Control и Position Sizing;
- исполнять ордера автоматически через брокерские API (Interactive Brokers, Alpaca, и др.).

### Ключевые характеристики

| Характеристика | Значение |
|---|---|
| Инструменты | Акции, ETF, Облигации, Фьючерсы |
| Временной горизонт | Долгосрочный (weeks–months) + краткосрочный (intraday) |
| Латентность исполнения | < 50ms (через Redis) |
| Частота переобучения AI | Еженедельно (walk-forward) |
| Максимальная просадка (hard limit) | 15% от NAV |
| Поддерживаемые брокеры | IBKR, Alpaca, Tinkoff, Bybit (через адаптеры) |

---

## Архитектура

```
┌─────────────────────────────────────────────────────────────────┐
│                    ВНЕШНИЕ ИСТОЧНИКИ ДАННЫХ                      │
│  Market APIs · News APIs · Macro Data · Social · SEC/EDGAR       │
└──────────────────────────┬──────────────────────────────────────┘
                           │  REST / WebSocket / FTP
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                  СЛОЙ СБОРА ДАННЫХ (Kafka)                       │
│  Market Data · News Intelligence · Macro/Political · Sentiment   │
└──────────────────────────┬──────────────────────────────────────┘
                           │  Events → Kafka Topics
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│               СЛОЙ АНАЛИЗА (PostgreSQL + Redis)                  │
│     Fundamental Analysis · Technical Analysis · Political Risk   │
└──────────────────────────┬──────────────────────────────────────┘
                           │  Features → Feature Store
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    AI PREDICTION ENGINE                          │
│  XGBoost · LightGBM · CatBoost · LSTM · Transformer Ensemble    │
└──────────────────────────┬──────────────────────────────────────┘
                           │  Signals → BUY / SELL / HOLD + Score
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│           PORTFOLIO OPTIMIZER + RISK ENGINE                      │
│   MPT · Black-Litterman · Risk Parity · VaR · ES · Drawdown     │
└──────────────────────────┬──────────────────────────────────────┘
                           │  Validated Orders
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    EXECUTION ENGINE                              │
│         Order Router · Smart OMS · Broker Adapters              │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│              MONITORING · ALERTING · AUDIT TRAIL                 │
│            Prometheus · Grafana · ELK · PagerDuty               │
└─────────────────────────────────────────────────────────────────┘
```

### Принципы проектирования

**Clean Architecture** — каждый сервис разделён на слои `domain → application → infrastructure → api`. Бизнес-логика не зависит от фреймворков и баз данных.

**Domain Driven Design** — каждый ограниченный контекст (Bounded Context) имеет собственные агрегаты, репозитории и доменные события.

**Event-Driven Architecture** — сервисы общаются через Kafka. Прямые HTTP-вызовы используются только для синхронных запросов (команды и запросы к API).

**SOLID** — интерфейсы репозиториев и сервисов абстрагированы; конкретные реализации подставляются через DI-контейнер.

---

## Стек технологий

| Категория | Технологии |
|---|---|
| Язык | Python 3.11+ |
| Web Framework | FastAPI 0.111+, Uvicorn, Pydantic v2 |
| Очередь сообщений | Apache Kafka 3.7+, kafka-python |
| Основная БД | PostgreSQL 15+ (asyncpg, SQLAlchemy 2.0 async) |
| Кэш / Feature Store | Redis 7.2+ (aioredis) |
| ML / AI | XGBoost, LightGBM, CatBoost, PyTorch, Transformers |
| Портфельная оптимизация | scipy, cvxpy, PyPortfolioOpt |
| Технический анализ | TA-Lib, pandas-ta |
| Бэктестинг | Backtrader, VectorBT |
| Эксперименты | MLflow, Optuna |
| Оркестрация пайплайнов | Apache Airflow 2.9+ |
| Контейнеризация | Docker, Docker Compose, Kubernetes (prod) |
| CI/CD | GitHub Actions |
| Мониторинг | Prometheus, Grafana, Alertmanager |
| Логирование | ELK Stack (Elasticsearch, Logstash, Kibana) |
| Тестирование | pytest, pytest-asyncio, pytest-cov, factory_boy |

---

## Структура репозитория

```
quantflow/
├── services/
│   ├── market_data/
│   │   ├── domain/
│   │   │   ├── entities/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── ohlcv.py
│   │   │   │   ├── ticker.py
│   │   │   │   └── orderbook.py
│   │   │   ├── value_objects/
│   │   │   │   ├── price.py
│   │   │   │   ├── volume.py
│   │   │   │   └── symbol.py
│   │   │   ├── repositories/
│   │   │   │   └── market_data_repository.py
│   │   │   └── events/
│   │   │       └── market_events.py
│   │   ├── application/
│   │   │   ├── use_cases/
│   │   │   │   ├── fetch_ohlcv.py
│   │   │   │   ├── stream_quotes.py
│   │   │   │   └── normalize_data.py
│   │   │   └── services/
│   │   │       └── market_data_service.py
│   │   ├── infrastructure/
│   │   │   ├── adapters/
│   │   │   │   ├── yahoo_finance_adapter.py
│   │   │   │   ├── polygon_adapter.py
│   │   │   │   └── alpaca_market_adapter.py
│   │   │   ├── repositories/
│   │   │   │   └── postgres_market_repository.py
│   │   │   ├── kafka/
│   │   │   │   ├── producer.py
│   │   │   │   └── consumer.py
│   │   │   └── cache/
│   │   │       └── redis_cache.py
│   │   ├── api/
│   │   │   ├── v1/
│   │   │   │   ├── router.py
│   │   │   │   ├── schemas.py
│   │   │   │   └── dependencies.py
│   │   │   └── main.py
│   │   ├── tests/
│   │   │   ├── unit/
│   │   │   ├── integration/
│   │   │   └── conftest.py
│   │   ├── Dockerfile
│   │   └── pyproject.toml
│   │
│   ├── news_intelligence/
│   ├── macroeconomic/
│   ├── political_risk/
│   ├── social_sentiment/
│   ├── fundamental_analysis/
│   ├── technical_analysis/
│   ├── ai_prediction_engine/
│   │   ├── domain/
│   │   ├── application/
│   │   ├── infrastructure/
│   │   │   ├── models/
│   │   │   │   ├── xgboost_model.py
│   │   │   │   ├── lightgbm_model.py
│   │   │   │   ├── catboost_model.py
│   │   │   │   ├── lstm_model.py
│   │   │   │   ├── transformer_model.py
│   │   │   │   └── ensemble_model.py
│   │   │   ├── feature_engineering/
│   │   │   └── training/
│   │   ├── api/
│   │   └── tests/
│   ├── portfolio_optimizer/
│   ├── risk_engine/
│   ├── execution_engine/
│   └── monitoring/
│
├── shared/
│   ├── domain/
│   │   ├── base_entity.py
│   │   ├── base_repository.py
│   │   ├── base_event.py
│   │   └── value_objects.py
│   ├── infrastructure/
│   │   ├── database/
│   │   │   ├── connection.py
│   │   │   └── migrations/
│   │   ├── kafka/
│   │   │   ├── base_producer.py
│   │   │   └── base_consumer.py
│   │   └── logging/
│   │       └── setup.py
│   └── utils/
│       ├── date_utils.py
│       ├── math_utils.py
│       └── validators.py
│
├── infra/
│   ├── docker/
│   │   ├── docker-compose.yml
│   │   ├── docker-compose.dev.yml
│   │   └── docker-compose.prod.yml
│   ├── kubernetes/
│   │   ├── deployments/
│   │   ├── services/
│   │   └── configmaps/
│   ├── kafka/
│   │   └── topics.yml
│   ├── postgres/
│   │   └── init.sql
│   └── grafana/
│       └── dashboards/
│
├── .github/
│   └── workflows/
│       ├── ci.yml
│       ├── cd.yml
│       └── model_retrain.yml
│
├── docs/
│   ├── architecture/
│   ├── api/
│   └── runbooks/
│
├── scripts/
│   ├── seed_data.py
│   ├── backtest_run.py
│   └── model_train.py
│
├── .env.example
├── pyproject.toml
├── Makefile
└── README.md
```

---

## Модули

### Market Data Service

**Назначение:** Сбор, нормализация и хранение рыночных данных (OHLCV, стакан, тики) по акциям, ETF, облигациям и фьючерсам в реальном времени и исторически.

**Входные данные:**
- REST/WebSocket от Yahoo Finance, Polygon.io, Alpaca, Interactive Brokers
- CSV-импорт исторических данных
- FIX-протокол (для институционального контура)

**Выходные данные:**
- Нормализованные OHLCV-бары (1m, 5m, 1h, 1d) в PostgreSQL
- Kafka-топик `market.quotes.raw`, `market.ohlcv.normalized`
- Redis-кэш последних котировок (TTL 1s)

**API:**
```
GET  /api/v1/market/ohlcv?symbol=AAPL&interval=1d&from=2024-01-01
GET  /api/v1/market/quote?symbol=AAPL
GET  /api/v1/market/orderbook?symbol=AAPL&depth=10
POST /api/v1/market/subscribe   {"symbols": ["AAPL", "MSFT"], "interval": "1m"}
WS   /ws/v1/market/stream
```

**Реализация:**

```python
# services/market_data/domain/entities/ohlcv.py
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4


@dataclass
class OHLCV:
    symbol: str
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    interval: str
    id: UUID = field(default_factory=uuid4)
    adjusted_close: Decimal | None = None
    vwap: Decimal | None = None

    def validate(self) -> None:
        if not (self.low <= self.open <= self.high):
            raise ValueError(f"Invalid OHLCV: open={self.open} not in [{self.low}, {self.high}]")
        if not (self.low <= self.close <= self.high):
            raise ValueError(f"Invalid OHLCV: close={self.close} not in [{self.low}, {self.high}]")
        if self.volume < 0:
            raise ValueError("Volume cannot be negative")

    @property
    def body_range(self) -> Decimal:
        return abs(self.close - self.open)

    @property
    def full_range(self) -> Decimal:
        return self.high - self.low
```

```python
# services/market_data/application/use_cases/fetch_ohlcv.py
from dataclasses import dataclass
from datetime import datetime

from ..domain.entities.ohlcv import OHLCV
from ..domain.repositories.market_data_repository import MarketDataRepository


@dataclass
class FetchOHLCVRequest:
    symbol: str
    interval: str
    from_date: datetime
    to_date: datetime
    adjusted: bool = True


class FetchOHLCVUseCase:
    def __init__(self, repository: MarketDataRepository) -> None:
        self._repository = repository

    async def execute(self, request: FetchOHLCVRequest) -> list[OHLCV]:
        bars = await self._repository.get_ohlcv(
            symbol=request.symbol,
            interval=request.interval,
            from_date=request.from_date,
            to_date=request.to_date,
        )
        for bar in bars:
            bar.validate()
        return bars
```

```python
# services/market_data/infrastructure/adapters/yahoo_finance_adapter.py
import asyncio
from datetime import datetime
from decimal import Decimal

import yfinance as yf

from ...domain.entities.ohlcv import OHLCV


class YahooFinanceAdapter:
    INTERVAL_MAP = {
        "1m": "1m", "5m": "5m", "15m": "15m",
        "1h": "60m", "1d": "1d", "1wk": "1wk",
    }

    async def fetch_ohlcv(
        self,
        symbol: str,
        interval: str,
        from_date: datetime,
        to_date: datetime,
    ) -> list[OHLCV]:
        yf_interval = self.INTERVAL_MAP.get(interval, "1d")
        ticker = yf.Ticker(symbol)

        raw = await asyncio.to_thread(
            ticker.history,
            start=from_date.strftime("%Y-%m-%d"),
            end=to_date.strftime("%Y-%m-%d"),
            interval=yf_interval,
            auto_adjust=True,
        )

        bars = []
        for ts, row in raw.iterrows():
            bar = OHLCV(
                symbol=symbol,
                timestamp=ts.to_pydatetime(),
                open=Decimal(str(row["Open"])),
                high=Decimal(str(row["High"])),
                low=Decimal(str(row["Low"])),
                close=Decimal(str(row["Close"])),
                volume=int(row["Volume"]),
                interval=interval,
            )
            bar.validate()
            bars.append(bar)
        return bars
```

```python
# services/market_data/api/v1/router.py
from datetime import datetime

from fastapi import APIRouter, Depends, Query

from ...application.use_cases.fetch_ohlcv import FetchOHLCVRequest, FetchOHLCVUseCase
from .dependencies import get_fetch_ohlcv_use_case
from .schemas import OHLCVResponse

router = APIRouter(prefix="/market", tags=["Market Data"])


@router.get("/ohlcv", response_model=list[OHLCVResponse])
async def get_ohlcv(
    symbol: str = Query(..., description="Ticker symbol, e.g. AAPL"),
    interval: str = Query("1d", description="Bar interval: 1m, 5m, 1h, 1d"),
    from_date: datetime = Query(...),
    to_date: datetime = Query(...),
    use_case: FetchOHLCVUseCase = Depends(get_fetch_ohlcv_use_case),
) -> list[OHLCVResponse]:
    request = FetchOHLCVRequest(
        symbol=symbol, interval=interval,
        from_date=from_date, to_date=to_date,
    )
    bars = await use_case.execute(request)
    return [OHLCVResponse.from_entity(b) for b in bars]
```

**Тесты:**

```python
# services/market_data/tests/unit/test_ohlcv.py
import pytest
from decimal import Decimal
from datetime import datetime

from ...domain.entities.ohlcv import OHLCV


def make_bar(**kwargs) -> OHLCV:
    defaults = dict(
        symbol="AAPL", timestamp=datetime(2024, 1, 1),
        open=Decimal("150.00"), high=Decimal("155.00"),
        low=Decimal("148.00"), close=Decimal("152.00"),
        volume=1_000_000, interval="1d",
    )
    return OHLCV(**{**defaults, **kwargs})


def test_valid_ohlcv_passes_validation():
    bar = make_bar()
    bar.validate()  # должен не бросить


def test_open_above_high_fails_validation():
    bar = make_bar(open=Decimal("160.00"))
    with pytest.raises(ValueError, match="open"):
        bar.validate()


def test_close_below_low_fails_validation():
    bar = make_bar(close=Decimal("140.00"))
    with pytest.raises(ValueError, match="close"):
        bar.validate()


def test_negative_volume_fails_validation():
    bar = make_bar(volume=-1)
    with pytest.raises(ValueError, match="Volume"):
        bar.validate()


def test_body_range_calculation():
    bar = make_bar(open=Decimal("150.00"), close=Decimal("152.00"))
    assert bar.body_range == Decimal("2.00")


def test_full_range_calculation():
    bar = make_bar(high=Decimal("155.00"), low=Decimal("148.00"))
    assert bar.full_range == Decimal("7.00")
```

**Docker:**

```dockerfile
# services/market_data/Dockerfile
FROM python:3.11-slim AS base
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

FROM base AS deps
COPY pyproject.toml .
RUN pip install --no-cache-dir hatch && hatch dep show requirements > requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

FROM base AS final
COPY --from=deps /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY . .
EXPOSE 8001
HEALTHCHECK --interval=30s --timeout=5s CMD curl -f http://localhost:8001/health || exit 1
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "2"]
```

---

### News Intelligence Service

**Назначение:** Агрегация новостей из множества источников, NLP-классификация по тональности, тематике и рыночной релевантности, подготовка новостных фич для AI Engine.

**Входные данные:**
- RSS/Atom-ленты (Reuters, Bloomberg, Financial Times, Seeking Alpha)
- NewsAPI, GDELT, Alpha Vantage News
- SEC EDGAR 8-K, 10-K, 10-Q, Earnings Releases

**Выходные данные:**
- Kafka-топик `news.articles.raw`, `news.sentiment.scored`
- Scoring по каждому тикеру: sentiment_score ∈ [-1, 1], relevance_score ∈ [0, 1]
- Named Entity Recognition: привязка статей к тикерам

**API:**
```
GET  /api/v1/news?symbol=AAPL&limit=50&from=2024-01-01
GET  /api/v1/news/sentiment?symbol=AAPL&window=24h
POST /api/v1/news/analyze   {"text": "...", "symbols": ["AAPL"]}
```

**Реализация:**

```python
# services/news_intelligence/domain/entities/article.py
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4


@dataclass
class NewsArticle:
    title: str
    content: str
    source: str
    published_at: datetime
    url: str
    id: UUID = field(default_factory=uuid4)
    sentiment_score: float | None = None       # [-1, 1]
    relevance_score: float | None = None       # [0, 1]
    related_symbols: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    language: str = "en"

    @property
    def is_scored(self) -> bool:
        return self.sentiment_score is not None

    @property
    def is_bearish(self) -> bool:
        return self.sentiment_score is not None and self.sentiment_score < -0.2

    @property
    def is_bullish(self) -> bool:
        return self.sentiment_score is not None and self.sentiment_score > 0.2
```

```python
# services/news_intelligence/application/services/sentiment_analyzer.py
from transformers import pipeline
import torch


class SentimentAnalyzer:
    """FinBERT-based sentiment analysis for financial news."""

    MODEL_NAME = "ProsusAI/finbert"

    def __init__(self) -> None:
        device = 0 if torch.cuda.is_available() else -1
        self._pipeline = pipeline(
            "text-classification",
            model=self.MODEL_NAME,
            device=device,
            truncation=True,
            max_length=512,
        )
        self._label_map = {"positive": 1.0, "neutral": 0.0, "negative": -1.0}

    def score(self, text: str) -> float:
        result = self._pipeline(text[:512])[0]
        label = result["label"].lower()
        confidence = result["score"]
        base_score = self._label_map.get(label, 0.0)
        return base_score * confidence

    def score_batch(self, texts: list[str]) -> list[float]:
        truncated = [t[:512] for t in texts]
        results = self._pipeline(truncated)
        scores = []
        for r in results:
            label = r["label"].lower()
            confidence = r["score"]
            scores.append(self._label_map.get(label, 0.0) * confidence)
        return scores
```

---

### Macroeconomic Service

**Назначение:** Сбор и анализ макроэкономических индикаторов, формирование макро-фич для портфельных решений.

**Источники данных:**
- FRED (Federal Reserve Economic Data) — GDP, CPI, безработица, M2
- World Bank, IMF Data API
- Eurostat, OECD.Stat
- U.S. Bureau of Labor Statistics

**Входные данные:** Расписание (Airflow DAG) + event-driven при выходе данных.

**Выходные данные:**
- Kafka-топик `macro.indicators.updated`
- Макро-вектор на символ: yield_curve_slope, cpi_yoy, gdp_growth, unemployment_rate, pmi, vix_level

**API:**
```
GET /api/v1/macro/indicators?series=GDP,CPI,UNRATE&from=2020-01-01
GET /api/v1/macro/regime          # текущий макрорежим: expansion/contraction/stagflation/recession
GET /api/v1/macro/forecast?horizon=3m
```

**Реализация:**

```python
# services/macroeconomic/infrastructure/adapters/fred_adapter.py
import asyncio
from datetime import datetime

import pandas as pd
from fredapi import Fred


class FREDAdapter:
    SERIES = {
        "gdp": "GDP",
        "cpi": "CPIAUCSL",
        "unemployment": "UNRATE",
        "fed_funds_rate": "FEDFUNDS",
        "yield_10y": "GS10",
        "yield_2y": "GS2",
        "m2": "M2SL",
        "pce": "PCE",
        "ism_manufacturing": "MANEMP",
    }

    def __init__(self, api_key: str) -> None:
        self._fred = Fred(api_key=api_key)

    async def fetch_series(self, series_id: str, from_date: datetime) -> pd.Series:
        return await asyncio.to_thread(
            self._fred.get_series,
            series_id,
            observation_start=from_date.strftime("%Y-%m-%d"),
        )

    async def fetch_all(self, from_date: datetime) -> dict[str, pd.Series]:
        tasks = {
            name: self.fetch_series(fred_id, from_date)
            for name, fred_id in self.SERIES.items()
        }
        results = {}
        for name, coro in tasks.items():
            results[name] = await coro
        return results

    def compute_yield_curve_slope(self, yield_10y: pd.Series, yield_2y: pd.Series) -> pd.Series:
        return yield_10y - yield_2y

    def detect_regime(self, gdp: float, cpi_yoy: float, unemployment: float) -> str:
        if gdp > 2.0 and unemployment < 5.0:
            return "expansion"
        if gdp < 0 and cpi_yoy > 4.0:
            return "stagflation"
        if gdp < 0:
            return "recession"
        return "contraction"
```

---

### Political Risk Service

**Назначение:** Оценка геополитических рисков, санкционных режимов, политической нестабильности по регионам — как дополнительный risk factor для Asset Allocation.

**Источники данных:**
- GDELT Project (геополитические события)
- PRS Group (Political Risk Services)
- Wikipedia Revision Frequency (прокси нестабильности)
- GPT-4/Claude для NER политических событий

**Выходные данные:**
- `political_risk_score` ∈ [0, 100] по стране/региону
- Kafka-топик `risk.political.updated`

**API:**
```
GET /api/v1/political/risk?country=RU&country=CN
GET /api/v1/political/events?region=eastern_europe&severity=high
GET /api/v1/political/sanctions?entity=COMPANY_NAME
```

---

### Social Sentiment Service

**Назначение:** Агрегация и анализ тональности в социальных сетях и форумах для формирования alternative data сигналов.

**Источники данных:**
- Reddit (r/wallstreetbets, r/investing, r/stocks) через Reddit API
- Twitter/X API v2 — тикерные упоминания
- StockTwits API
- Telegram-каналы (через Telethon)

**Реализация:**

```python
# services/social_sentiment/application/services/reddit_sentiment.py
import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta

import asyncpraw

from ..domain.entities.sentiment_signal import SentimentSignal


@dataclass
class RedditSentimentConfig:
    client_id: str
    client_secret: str
    user_agent: str
    subreddits: list[str]


class RedditSentimentCollector:
    def __init__(self, config: RedditSentimentConfig, analyzer) -> None:
        self._config = config
        self._analyzer = analyzer

    async def collect(self, symbol: str, hours: int = 24) -> list[SentimentSignal]:
        reddit = asyncpraw.Reddit(
            client_id=self._config.client_id,
            client_secret=self._config.client_secret,
            user_agent=self._config.user_agent,
        )
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        signals = []

        for subreddit_name in self._config.subreddits:
            subreddit = await reddit.subreddit(subreddit_name)
            async for submission in subreddit.search(symbol, limit=100):
                if datetime.utcfromtimestamp(submission.created_utc) < cutoff:
                    continue
                score = self._analyzer.score(f"{submission.title} {submission.selftext}")
                signals.append(SentimentSignal(
                    symbol=symbol,
                    source=f"reddit/{subreddit_name}",
                    score=score,
                    upvotes=submission.score,
                    timestamp=datetime.utcfromtimestamp(submission.created_utc),
                ))

        await reddit.close()
        return signals
```

---

### Fundamental Analysis Service

**Назначение:** Вычисление фундаментальных метрик компаний на основе финансовой отчётности. Генерация фундаментальных фич для AI Engine.

**Входные данные:**
- SEC EDGAR (10-K, 10-Q, 8-K через EDGAR API)
- Simfin, Financial Modeling Prep API
- Yahoo Finance Financials

**Вычисляемые метрики:**

| Категория | Метрики |
|---|---|
| Оценка | P/E, P/B, P/S, EV/EBITDA, EV/Revenue |
| Качество | ROE, ROA, ROIC, Gross Margin, Operating Margin |
| Рост | Revenue Growth YoY, EPS Growth, FCF Growth |
| Долг | Debt/Equity, Interest Coverage, Net Debt/EBITDA |
| Ликвидность | Current Ratio, Quick Ratio |
| Piotroski F-Score | Совокупный score [0–9] |

**Реализация:**

```python
# services/fundamental_analysis/domain/value_objects/financial_ratios.py
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class FinancialRatios:
    symbol: str

    # Valuation
    pe_ratio: Decimal | None = None
    pb_ratio: Decimal | None = None
    ps_ratio: Decimal | None = None
    ev_ebitda: Decimal | None = None

    # Profitability
    roe: Decimal | None = None
    roa: Decimal | None = None
    roic: Decimal | None = None
    gross_margin: Decimal | None = None
    operating_margin: Decimal | None = None
    net_margin: Decimal | None = None

    # Growth
    revenue_growth_yoy: Decimal | None = None
    eps_growth_yoy: Decimal | None = None
    fcf_growth_yoy: Decimal | None = None

    # Leverage
    debt_to_equity: Decimal | None = None
    interest_coverage: Decimal | None = None
    net_debt_to_ebitda: Decimal | None = None

    # Liquidity
    current_ratio: Decimal | None = None
    quick_ratio: Decimal | None = None

    # Composite
    piotroski_score: int | None = None  # 0–9

    @property
    def is_value_candidate(self) -> bool:
        return (
            self.pe_ratio is not None and self.pe_ratio < Decimal("15")
            and self.pb_ratio is not None and self.pb_ratio < Decimal("2")
            and self.piotroski_score is not None and self.piotroski_score >= 7
        )

    @property
    def quality_score(self) -> float:
        scores = []
        if self.roe is not None:
            scores.append(min(float(self.roe) / 0.20, 1.0))
        if self.gross_margin is not None:
            scores.append(min(float(self.gross_margin) / 0.50, 1.0))
        if self.interest_coverage is not None:
            scores.append(min(float(self.interest_coverage) / 10.0, 1.0))
        return sum(scores) / len(scores) if scores else 0.0
```

---

### Technical Analysis Service

**Назначение:** Вычисление технических индикаторов, паттернов и уровней поддержки/сопротивления.

**Реализация:**

```python
# services/technical_analysis/application/services/indicator_calculator.py
import pandas as pd
import pandas_ta as ta
import numpy as np
from dataclasses import dataclass


@dataclass
class TechnicalFeatures:
    symbol: str
    timestamp: pd.Timestamp

    # Trend
    sma_20: float | None = None
    sma_50: float | None = None
    sma_200: float | None = None
    ema_12: float | None = None
    ema_26: float | None = None
    macd: float | None = None
    macd_signal: float | None = None
    macd_hist: float | None = None
    adx: float | None = None

    # Momentum
    rsi_14: float | None = None
    stoch_k: float | None = None
    stoch_d: float | None = None
    williams_r: float | None = None
    cci: float | None = None
    mfi: float | None = None

    # Volatility
    bb_upper: float | None = None
    bb_middle: float | None = None
    bb_lower: float | None = None
    bb_width: float | None = None
    atr_14: float | None = None
    natr: float | None = None

    # Volume
    obv: float | None = None
    vwap: float | None = None
    cmf: float | None = None
    ad_line: float | None = None

    # Price Action
    support_level: float | None = None
    resistance_level: float | None = None
    trend_direction: str | None = None  # "up" | "down" | "sideways"


class IndicatorCalculator:
    def compute(self, df: pd.DataFrame) -> list[TechnicalFeatures]:
        df = df.copy()
        df.ta.strategy("all")

        features = []
        for i in range(len(df)):
            row = df.iloc[i]
            f = TechnicalFeatures(
                symbol=df.attrs.get("symbol", "UNKNOWN"),
                timestamp=df.index[i],
                sma_20=self._safe(row, "SMA_20"),
                sma_50=self._safe(row, "SMA_50"),
                sma_200=self._safe(row, "SMA_200"),
                ema_12=self._safe(row, "EMA_12"),
                ema_26=self._safe(row, "EMA_26"),
                macd=self._safe(row, "MACD_12_26_9"),
                macd_signal=self._safe(row, "MACDs_12_26_9"),
                macd_hist=self._safe(row, "MACDh_12_26_9"),
                rsi_14=self._safe(row, "RSI_14"),
                bb_upper=self._safe(row, "BBU_5_2.0"),
                bb_lower=self._safe(row, "BBL_5_2.0"),
                atr_14=self._safe(row, "ATRr_14"),
                obv=self._safe(row, "OBV"),
                adx=self._safe(row, "ADX_14"),
            )
            features.append(f)
        return features

    @staticmethod
    def _safe(row: pd.Series, col: str) -> float | None:
        val = row.get(col)
        return float(val) if val is not None and not np.isnan(val) else None
```

---

### AI Prediction Engine

**Назначение:** Генерация торговых сигналов BUY / SELL / HOLD с вероятностными оценками. Гибридный ансамбль из 5 моделей с meta-learner на втором уровне.

**Архитектура Ensemble:**

```
Уровень 1 (Base Models):
  ├── XGBoost       → P(BUY), P(SELL), P(HOLD)
  ├── LightGBM      → P(BUY), P(SELL), P(HOLD)
  ├── CatBoost      → P(BUY), P(SELL), P(HOLD)
  ├── LSTM          → P(BUY), P(SELL), P(HOLD)
  └── TFT           → P(BUY), P(SELL), P(HOLD)

Уровень 2 (Meta-Learner):
  └── Logistic Regression (Stacking)
      → Final Signal + Confidence Score
```

**Реализация:**

```python
# services/ai_prediction_engine/infrastructure/models/ensemble_model.py
from __future__ import annotations

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from .xgboost_model import XGBoostModel
from .lightgbm_model import LightGBMModel
from .catboost_model import CatBoostModel
from .lstm_model import LSTMModel
from .transformer_model import TFTModel


class EnsembleModel:
    """Two-level stacking ensemble: 5 base models + logistic meta-learner."""

    SIGNAL_MAP = {0: "HOLD", 1: "BUY", 2: "SELL"}

    def __init__(self) -> None:
        self._base_models = [
            XGBoostModel(),
            LightGBMModel(),
            CatBoostModel(),
            LSTMModel(),
            TFTModel(),
        ]
        self._meta_learner = LogisticRegression(
            C=1.0, max_iter=1000, multi_class="multinomial"
        )
        self._scaler = StandardScaler()
        self._is_fitted = False

    def fit(self, X: np.ndarray, y: np.ndarray, X_val: np.ndarray, y_val: np.ndarray) -> None:
        meta_features_train = []
        for model in self._base_models:
            model.fit(X, y)
            proba = model.predict_proba(X_val)   # shape (n, 3)
            meta_features_train.append(proba)

        meta_X = np.hstack(meta_features_train)  # shape (n, 15)
        meta_X_scaled = self._scaler.fit_transform(meta_X)
        self._meta_learner.fit(meta_X_scaled, y_val)
        self._is_fitted = True

    def predict(self, X: np.ndarray) -> list[dict]:
        if not self._is_fitted:
            raise RuntimeError("Ensemble is not fitted. Call fit() first.")

        meta_features = []
        for model in self._base_models:
            proba = model.predict_proba(X)
            meta_features.append(proba)

        meta_X = np.hstack(meta_features)
        meta_X_scaled = self._scaler.transform(meta_X)
        final_proba = self._meta_learner.predict_proba(meta_X_scaled)
        final_class = np.argmax(final_proba, axis=1)

        results = []
        for i in range(len(X)):
            signal = self.SIGNAL_MAP[final_class[i]]
            confidence = float(np.max(final_proba[i]))
            results.append({
                "signal": signal,
                "confidence": confidence,
                "probabilities": {
                    "HOLD": float(final_proba[i][0]),
                    "BUY":  float(final_proba[i][1]),
                    "SELL": float(final_proba[i][2]),
                },
                "model_votes": {
                    m.__class__.__name__: self.SIGNAL_MAP[np.argmax(meta_features[j][i])]
                    for j, m in enumerate(self._base_models)
                },
            })
        return results
```

```python
# services/ai_prediction_engine/infrastructure/models/lstm_model.py
from __future__ import annotations

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset


class LSTMNet(nn.Module):
    def __init__(self, input_size: int, hidden_size: int = 128, num_layers: int = 2,
                 dropout: float = 0.2, num_classes: int = 3) -> None:
        super().__init__()
        self.lstm = nn.LSTM(
            input_size, hidden_size, num_layers,
            batch_first=True, dropout=dropout, bidirectional=False,
        )
        self.attention = nn.MultiheadAttention(hidden_size, num_heads=4, batch_first=True)
        self.norm = nn.LayerNorm(hidden_size)
        self.classifier = nn.Sequential(
            nn.Linear(hidden_size, 64),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        lstm_out, _ = self.lstm(x)                      # (B, T, H)
        attn_out, _ = self.attention(lstm_out, lstm_out, lstm_out)
        out = self.norm(lstm_out + attn_out)             # residual
        return self.classifier(out[:, -1, :])            # last timestep


class LSTMModel:
    def __init__(self, sequence_length: int = 60, input_size: int = 64,
                 epochs: int = 50, lr: float = 1e-3, batch_size: int = 64) -> None:
        self.sequence_length = sequence_length
        self.input_size = input_size
        self.epochs = epochs
        self.lr = lr
        self.batch_size = batch_size
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self._net: LSTMNet | None = None

    def _build_sequences(self, X: np.ndarray) -> np.ndarray:
        seqs = []
        for i in range(self.sequence_length, len(X)):
            seqs.append(X[i - self.sequence_length:i])
        return np.array(seqs)

    def fit(self, X: np.ndarray, y: np.ndarray) -> None:
        X_seq = self._build_sequences(X)
        y_seq = y[self.sequence_length:]

        self._net = LSTMNet(self.input_size).to(self.device)
        optimizer = torch.optim.Adam(self._net.parameters(), lr=self.lr)
        criterion = nn.CrossEntropyLoss()
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=5)

        dataset = TensorDataset(
            torch.FloatTensor(X_seq),
            torch.LongTensor(y_seq),
        )
        loader = DataLoader(dataset, batch_size=self.batch_size, shuffle=True)

        self._net.train()
        for epoch in range(self.epochs):
            total_loss = 0.0
            for xb, yb in loader:
                xb, yb = xb.to(self.device), yb.to(self.device)
                optimizer.zero_grad()
                loss = criterion(self._net(xb), yb)
                loss.backward()
                nn.utils.clip_grad_norm_(self._net.parameters(), max_norm=1.0)
                optimizer.step()
                total_loss += loss.item()
            scheduler.step(total_loss)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if self._net is None:
            raise RuntimeError("Model not fitted.")
        X_seq = self._build_sequences(X)
        self._net.eval()
        with torch.no_grad():
            tensor = torch.FloatTensor(X_seq).to(self.device)
            logits = self._net(tensor)
            proba = torch.softmax(logits, dim=1).cpu().numpy()
        return proba
```

---

### Portfolio Optimizer

**Назначение:** Оптимизация весов портфеля с учётом сигналов AI Engine, макро-режима и ограничений Risk Engine.

**Методы оптимизации:**

**1. Modern Portfolio Theory (Markowitz):**
```
max μᵀw − (λ/2) wᵀΣw
s.t. 1ᵀw = 1, w ≥ 0, wᵢ ≤ max_weight
```

**2. Black-Litterman:**
```
μ_BL = [(τΣ)⁻¹ + PᵀΩ⁻¹P]⁻¹ [(τΣ)⁻¹μ_eq + PᵀΩ⁻¹q]
```
где q — прогнозы доходности от AI Engine, Ω — матрица неопределённости взглядов.

**3. Risk Parity:**
```
min Σᵢ(RCᵢ − 1/n)²
где RCᵢ = wᵢ · (Σw)ᵢ / σₚ
```

**Реализация:**

```python
# services/portfolio_optimizer/application/services/black_litterman.py
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize


class BlackLittermanOptimizer:
    """Black-Litterman model with AI Engine views integration."""

    def __init__(self, risk_aversion: float = 3.0, tau: float = 0.05) -> None:
        self.risk_aversion = risk_aversion
        self.tau = tau

    def compute_equilibrium_returns(
        self, weights_mkt: np.ndarray, cov_matrix: np.ndarray
    ) -> np.ndarray:
        return self.risk_aversion * cov_matrix @ weights_mkt

    def combine_views(
        self,
        cov_matrix: np.ndarray,
        mu_eq: np.ndarray,
        P: np.ndarray,
        q: np.ndarray,
        omega: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        tau_sigma = self.tau * cov_matrix
        tau_sigma_inv = np.linalg.inv(tau_sigma)
        omega_inv = np.linalg.inv(omega)

        posterior_cov_inv = tau_sigma_inv + P.T @ omega_inv @ P
        posterior_cov = np.linalg.inv(posterior_cov_inv)
        posterior_mu = posterior_cov @ (tau_sigma_inv @ mu_eq + P.T @ omega_inv @ q)

        return posterior_mu, posterior_cov

    def optimize(
        self,
        expected_returns: np.ndarray,
        cov_matrix: np.ndarray,
        constraints: dict | None = None,
    ) -> np.ndarray:
        n = len(expected_returns)
        constraints = constraints or {}
        max_weight = constraints.get("max_weight", 0.25)
        min_weight = constraints.get("min_weight", 0.0)

        def neg_sharpe(w: np.ndarray) -> float:
            port_return = expected_returns @ w
            port_vol = np.sqrt(w @ cov_matrix @ w)
            return -(port_return / port_vol) if port_vol > 0 else 0.0

        bounds = [(min_weight, max_weight)] * n
        cons = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]

        result = minimize(
            neg_sharpe,
            x0=np.ones(n) / n,
            method="SLSQP",
            bounds=bounds,
            constraints=cons,
            options={"maxiter": 1000, "ftol": 1e-9},
        )
        return result.x if result.success else np.ones(n) / n


class RiskParityOptimizer:
    """Equal Risk Contribution portfolio."""

    def optimize(self, cov_matrix: np.ndarray) -> np.ndarray:
        n = cov_matrix.shape[0]

        def risk_budget_objective(w: np.ndarray) -> float:
            w = np.array(w)
            port_var = w @ cov_matrix @ w
            port_vol = np.sqrt(port_var)
            marginal_contrib = cov_matrix @ w
            risk_contrib = w * marginal_contrib / port_vol
            target = port_vol / n
            return float(np.sum((risk_contrib - target) ** 2))

        result = minimize(
            risk_budget_objective,
            x0=np.ones(n) / n,
            method="SLSQP",
            bounds=[(0.0, 1.0)] * n,
            constraints=[{"type": "eq", "fun": lambda w: np.sum(w) - 1}],
        )
        return result.x if result.success else np.ones(n) / n
```

---

### Risk Engine

**Назначение:** Центральный шлюз управления риском. Блокирует исполнение ордеров при нарушении любого из риск-лимитов.

**Реализованные методы:**

| Метод | Описание |
|---|---|
| VaR (Parametric) | 95%/99% однодневный Value at Risk |
| VaR (Historical) | 250-дневное историческое окно |
| VaR (Monte Carlo) | 10 000 симуляций, Cholesky decomposition |
| Expected Shortfall | CVaR — среднее за хвостом VaR |
| Max Drawdown Control | Circuit breaker при превышении 15% просадки |
| Position Sizing | Kelly Criterion + фиксированный процент от NAV |
| Portfolio Exposure | Лимиты по секторам, странам, отдельным именам |

**Реализация:**

```python
# services/risk_engine/application/services/var_calculator.py
from __future__ import annotations

import numpy as np
from scipy import stats
from dataclasses import dataclass


@dataclass
class VaRResult:
    parametric_95: float
    parametric_99: float
    historical_95: float
    historical_99: float
    monte_carlo_95: float
    monte_carlo_99: float
    expected_shortfall_95: float
    expected_shortfall_99: float
    portfolio_value: float

    @property
    def worst_case_loss(self) -> float:
        return max(
            self.parametric_99,
            self.historical_99,
            self.monte_carlo_99,
        )


class VaRCalculator:
    def __init__(self, n_simulations: int = 10_000) -> None:
        self.n_simulations = n_simulations

    def compute(
        self,
        returns: np.ndarray,
        weights: np.ndarray,
        portfolio_value: float,
        cov_matrix: np.ndarray,
    ) -> VaRResult:
        port_returns = returns @ weights
        mu = np.mean(port_returns)
        sigma = np.std(port_returns)

        # Parametric VaR
        p_var_95 = portfolio_value * (mu - stats.norm.ppf(0.95) * sigma)
        p_var_99 = portfolio_value * (mu - stats.norm.ppf(0.99) * sigma)

        # Historical VaR
        sorted_returns = np.sort(port_returns)
        h_var_95 = portfolio_value * abs(np.percentile(sorted_returns, 5))
        h_var_99 = portfolio_value * abs(np.percentile(sorted_returns, 1))

        # Monte Carlo VaR
        L = np.linalg.cholesky(cov_matrix + 1e-8 * np.eye(len(weights)))
        z = np.random.standard_normal((self.n_simulations, len(weights)))
        sim_returns = (z @ L.T) @ weights
        mc_var_95 = portfolio_value * abs(np.percentile(sim_returns, 5))
        mc_var_99 = portfolio_value * abs(np.percentile(sim_returns, 1))

        # Expected Shortfall (CVaR)
        es_95 = portfolio_value * abs(sorted_returns[sorted_returns <= np.percentile(sorted_returns, 5)].mean())
        es_99 = portfolio_value * abs(sorted_returns[sorted_returns <= np.percentile(sorted_returns, 1)].mean())

        return VaRResult(
            parametric_95=p_var_95, parametric_99=p_var_99,
            historical_95=h_var_95, historical_99=h_var_99,
            monte_carlo_95=mc_var_95, monte_carlo_99=mc_var_99,
            expected_shortfall_95=es_95, expected_shortfall_99=es_99,
            portfolio_value=portfolio_value,
        )


class DrawdownController:
    def __init__(self, max_drawdown: float = 0.15) -> None:
        self.max_drawdown = max_drawdown
        self._peak_nav = 0.0

    def update(self, current_nav: float) -> None:
        if current_nav > self._peak_nav:
            self._peak_nav = current_nav

    @property
    def current_drawdown(self) -> float:
        if self._peak_nav == 0:
            return 0.0
        return (self._peak_nav - self._peak_nav) / self._peak_nav  # corrected at runtime

    def is_circuit_breaker_triggered(self, current_nav: float) -> bool:
        if self._peak_nav == 0:
            return False
        drawdown = (self._peak_nav - current_nav) / self._peak_nav
        return drawdown >= self.max_drawdown


class PositionSizer:
    def __init__(self, max_risk_per_trade: float = 0.02) -> None:
        self.max_risk_per_trade = max_risk_per_trade

    def kelly_size(
        self,
        win_prob: float,
        win_loss_ratio: float,
        portfolio_value: float,
    ) -> float:
        """Fractional Kelly Criterion (half-Kelly for safety)."""
        kelly_fraction = (win_prob * win_loss_ratio - (1 - win_prob)) / win_loss_ratio
        half_kelly = max(0.0, kelly_fraction / 2)
        max_risk_size = portfolio_value * self.max_risk_per_trade
        return min(portfolio_value * half_kelly, max_risk_size)

    def fixed_fraction_size(
        self,
        portfolio_value: float,
        stop_loss_pct: float,
    ) -> float:
        """Risk fixed percentage of NAV per trade."""
        if stop_loss_pct <= 0:
            return 0.0
        return (portfolio_value * self.max_risk_per_trade) / stop_loss_pct
```

---

### Execution Engine

**Назначение:** Приём валидированных ордеров от Risk Engine, маршрутизация к брокерским адаптерам, управление жизненным циклом ордеров.

**Поддерживаемые типы ордеров:** Market, Limit, Stop, Stop-Limit, Trailing Stop, MOC/MOO.

**Реализация:**

```python
# services/execution_engine/domain/entities/order.py
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID, uuid4


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"
    TRAILING_STOP = "TRAILING_STOP"


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


@dataclass
class Order:
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: Decimal
    id: UUID = field(default_factory=uuid4)
    limit_price: Decimal | None = None
    stop_price: Decimal | None = None
    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None
    status: OrderStatus = OrderStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    filled_at: datetime | None = None
    filled_price: Decimal | None = None
    filled_quantity: Decimal = Decimal("0")
    broker_order_id: str | None = None
    strategy_id: str | None = None

    def fill(self, price: Decimal, quantity: Decimal) -> None:
        self.filled_quantity += quantity
        self.filled_price = price
        if self.filled_quantity >= self.quantity:
            self.status = OrderStatus.FILLED
            self.filled_at = datetime.utcnow()
        else:
            self.status = OrderStatus.PARTIALLY_FILLED

    @property
    def is_terminal(self) -> bool:
        return self.status in {
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED,
            OrderStatus.EXPIRED,
        }
```

```python
# services/execution_engine/infrastructure/adapters/alpaca_adapter.py
import asyncio
from decimal import Decimal

import alpaca_trade_api as tradeapi

from ...domain.entities.order import Order, OrderStatus


class AlpacaBrokerAdapter:
    def __init__(self, api_key: str, secret_key: str, base_url: str) -> None:
        self._api = tradeapi.REST(api_key, secret_key, base_url)

    async def submit_order(self, order: Order) -> str:
        kwargs = {
            "symbol": order.symbol,
            "qty": str(order.quantity),
            "side": order.side.value.lower(),
            "type": order.order_type.value.lower(),
            "time_in_force": "day",
        }
        if order.limit_price:
            kwargs["limit_price"] = str(order.limit_price)
        if order.stop_price:
            kwargs["stop_price"] = str(order.stop_price)

        response = await asyncio.to_thread(self._api.submit_order, **kwargs)
        return response.id

    async def cancel_order(self, broker_order_id: str) -> None:
        await asyncio.to_thread(self._api.cancel_order, broker_order_id)

    async def get_order_status(self, broker_order_id: str) -> OrderStatus:
        order = await asyncio.to_thread(self._api.get_order, broker_order_id)
        status_map = {
            "new": OrderStatus.SUBMITTED,
            "partially_filled": OrderStatus.PARTIALLY_FILLED,
            "filled": OrderStatus.FILLED,
            "canceled": OrderStatus.CANCELLED,
            "rejected": OrderStatus.REJECTED,
            "expired": OrderStatus.EXPIRED,
        }
        return status_map.get(order.status, OrderStatus.PENDING)
```

---

### Monitoring Service

**Назначение:** Централизованный мониторинг health-состояния всех сервисов, производительности AI-моделей, P&L и системных метрик.

**Реализация:**

```python
# services/monitoring/application/services/performance_tracker.py
from dataclasses import dataclass, field
from datetime import datetime
import numpy as np


@dataclass
class PortfolioMetrics:
    as_of: datetime
    nav: float
    total_return: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    max_drawdown: float
    current_drawdown: float
    win_rate: float
    profit_factor: float
    average_trade: float
    volatility_annualized: float
    beta: float
    alpha: float
    information_ratio: float


class PerformanceTracker:
    def __init__(self, risk_free_rate: float = 0.05) -> None:
        self.risk_free_rate = risk_free_rate
        self._nav_history: list[tuple[datetime, float]] = []

    def update(self, nav: float) -> None:
        self._nav_history.append((datetime.utcnow(), nav))

    def compute_metrics(self, benchmark_returns: np.ndarray | None = None) -> PortfolioMetrics:
        navs = np.array([v for _, v in self._nav_history])
        returns = np.diff(navs) / navs[:-1]
        daily_rf = self.risk_free_rate / 252
        excess = returns - daily_rf

        sharpe = (np.mean(excess) / np.std(returns)) * np.sqrt(252) if np.std(returns) > 0 else 0
        downside = returns[returns < 0]
        sortino = (np.mean(excess) / np.std(downside)) * np.sqrt(252) if len(downside) > 0 and np.std(downside) > 0 else 0

        cumulative = navs / navs[0]
        rolling_max = np.maximum.accumulate(cumulative)
        drawdowns = (cumulative - rolling_max) / rolling_max
        max_dd = abs(drawdowns.min())
        current_dd = abs(drawdowns[-1])

        annual_return = (navs[-1] / navs[0]) ** (252 / len(navs)) - 1
        calmar = annual_return / max_dd if max_dd > 0 else 0

        return PortfolioMetrics(
            as_of=datetime.utcnow(),
            nav=navs[-1],
            total_return=float((navs[-1] / navs[0]) - 1),
            sharpe_ratio=float(sharpe),
            sortino_ratio=float(sortino),
            calmar_ratio=float(calmar),
            max_drawdown=float(max_dd),
            current_drawdown=float(current_dd),
            win_rate=float(np.mean(returns > 0)),
            profit_factor=0.0,  # computed from trade log
            average_trade=float(np.mean(returns)),
            volatility_annualized=float(np.std(returns) * np.sqrt(252)),
            beta=0.0,
            alpha=0.0,
            information_ratio=0.0,
        )
```

---

## Быстрый старт

### Требования

- Docker 24+ и Docker Compose v2
- Python 3.11+
- Make (опционально, для удобства)
- 16 GB RAM рекомендуется (AI models in-memory)

### Клонирование и настройка

```bash
git clone https://github.com/your-org/quantflow.git
cd quantflow

cp .env.example .env
# Заполните переменные окружения (см. раздел Конфигурация)
nano .env
```

### Запуск инфраструктуры

```bash
# Поднять PostgreSQL, Redis, Kafka, Zookeeper
make infra-up
# или
docker compose -f infra/docker/docker-compose.yml up -d

# Проверить статус
docker compose ps
```

### Запуск всех сервисов

```bash
# Режим разработки (с hot-reload)
make dev
# или
docker compose -f infra/docker/docker-compose.dev.yml up --build

# Только конкретный сервис
docker compose up market_data --build
```

### Инициализация БД

```bash
make db-migrate
# или
docker compose exec market_data alembic upgrade head
docker compose exec fundamental_analysis alembic upgrade head
# ... для каждого сервиса
```

### Заполнение исторических данных

```bash
# Загрузить 5 лет исторических данных по S&P 500
python scripts/seed_data.py --universe sp500 --years 5

# Только указанные тикеры
python scripts/seed_data.py --symbols AAPL MSFT GOOGL AMZN NVDA --years 3
```

### Первичное обучение моделей

```bash
# Обучить все модели ансамбля
python scripts/model_train.py --universe sp500 --start 2018-01-01

# Запустить бэктест
python scripts/backtest_run.py --strategy ensemble --start 2020-01-01 --end 2024-12-31
```

---

## Конфигурация

Все настройки передаются через переменные окружения. Создайте `.env` из `.env.example`:

```dotenv
# ─── Database ────────────────────────────────────────────────────
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=quantflow
POSTGRES_USER=quantflow
POSTGRES_PASSWORD=your_secure_password

# ─── Redis ───────────────────────────────────────────────────────
REDIS_URL=redis://localhost:6379/0

# ─── Kafka ───────────────────────────────────────────────────────
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_GROUP_ID=quantflow

# ─── Market Data APIs ────────────────────────────────────────────
POLYGON_API_KEY=your_polygon_key
ALPACA_API_KEY=your_alpaca_key
ALPACA_SECRET_KEY=your_alpaca_secret
ALPACA_BASE_URL=https://paper-api.alpaca.markets  # paper trading

# ─── News APIs ───────────────────────────────────────────────────
NEWS_API_KEY=your_newsapi_key
REDDIT_CLIENT_ID=your_reddit_client_id
REDDIT_CLIENT_SECRET=your_reddit_secret
REDDIT_USER_AGENT=QuantFlow/1.0

# ─── Macro Data ──────────────────────────────────────────────────
FRED_API_KEY=your_fred_key

# ─── Broker ──────────────────────────────────────────────────────
IBKR_HOST=127.0.0.1
IBKR_PORT=7497
IBKR_CLIENT_ID=1
BROKER=alpaca  # alpaca | ibkr | paper

# ─── AI / ML ─────────────────────────────────────────────────────
MLFLOW_TRACKING_URI=http://localhost:5000
MODEL_REGISTRY_PATH=/models
RETRAIN_SCHEDULE=0 0 * * 1  # каждый понедельник в 00:00

# ─── Risk Limits ─────────────────────────────────────────────────
MAX_DRAWDOWN=0.15
MAX_POSITION_SIZE=0.10
MAX_SECTOR_EXPOSURE=0.30
MAX_DAILY_VAR_95=0.02
RISK_FREE_RATE=0.05

# ─── Portfolio ───────────────────────────────────────────────────
OPTIMIZATION_METHOD=black_litterman  # mpt | black_litterman | risk_parity
REBALANCE_FREQUENCY=weekly
MIN_SIGNAL_CONFIDENCE=0.65

# ─── Monitoring ──────────────────────────────────────────────────
PROMETHEUS_PORT=9090
GRAFANA_PORT=3000
LOG_LEVEL=INFO
SENTRY_DSN=your_sentry_dsn

# ─── Paper Trading ───────────────────────────────────────────────
PAPER_TRADING=true
INITIAL_CAPITAL=100000
```

---

## API Документация

После запуска сервисов документация доступна по адресам:

| Сервис | Swagger UI | ReDoc |
|---|---|---|
| Market Data | http://localhost:8001/docs | http://localhost:8001/redoc |
| News Intelligence | http://localhost:8002/docs | http://localhost:8002/redoc |
| Macroeconomic | http://localhost:8003/docs | http://localhost:8003/redoc |
| AI Prediction | http://localhost:8007/docs | http://localhost:8007/redoc |
| Portfolio Optimizer | http://localhost:8008/docs | http://localhost:8008/redoc |
| Risk Engine | http://localhost:8009/docs | http://localhost:8009/redoc |
| Execution Engine | http://localhost:8010/docs | http://localhost:8010/redoc |

### Примеры запросов

```bash
# Получить сигнал для AAPL
curl http://localhost:8007/api/v1/predict \
  -H "Content-Type: application/json" \
  -d '{"symbols": ["AAPL"], "horizon": "5d"}'

# Получить оптимальные веса портфеля
curl http://localhost:8008/api/v1/optimize \
  -H "Content-Type: application/json" \
  -d '{"symbols": ["AAPL","MSFT","GOOGL"], "method": "black_litterman"}'

# Проверить VaR портфеля
curl http://localhost:8009/api/v1/var \
  -H "Content-Type: application/json" \
  -d '{"portfolio": {"AAPL": 0.3, "MSFT": 0.4, "GOOGL": 0.3}, "nav": 100000}'

# Разместить ордер (paper trading)
curl -X POST http://localhost:8010/api/v1/orders \
  -H "Content-Type: application/json" \
  -d '{"symbol": "AAPL", "side": "BUY", "quantity": 10, "order_type": "LIMIT", "limit_price": 185.00}'
```

---

## Тестирование

### Запуск тестов

```bash
# Все тесты
make test

# Unit-тесты (быстро, без зависимостей)
pytest services/ -m unit -v --cov=services --cov-report=term-missing

# Integration-тесты (требуют запущенных контейнеров)
pytest services/ -m integration -v

# Конкретный сервис
pytest services/risk_engine/tests/ -v

# С покрытием
pytest --cov=services --cov-report=html --cov-fail-under=80
open htmlcov/index.html
```

### Структура тестов

Каждый сервис содержит:

```
tests/
├── unit/                   # Тесты без внешних зависимостей
│   ├── test_entities.py
│   ├── test_use_cases.py
│   └── test_value_objects.py
├── integration/            # Тесты с реальными БД/Kafka
│   ├── test_repository.py
│   └── test_kafka_producer.py
├── e2e/                    # End-to-end тесты
│   └── test_signal_pipeline.py
└── conftest.py             # Фикстуры, фабрики
```

### Пример integration-теста

```python
# services/market_data/tests/integration/test_repository.py
import pytest
from datetime import datetime, timedelta
from decimal import Decimal

from ...infrastructure.repositories.postgres_market_repository import PostgresMarketRepository


@pytest.mark.integration
@pytest.mark.asyncio
async def test_save_and_retrieve_ohlcv(pg_repository: PostgresMarketRepository):
    bar = make_bar(symbol="TSLA", close=Decimal("250.00"))
    await pg_repository.save(bar)

    results = await pg_repository.get_ohlcv(
        symbol="TSLA",
        interval="1d",
        from_date=datetime.utcnow() - timedelta(days=1),
        to_date=datetime.utcnow(),
    )
    assert len(results) == 1
    assert results[0].symbol == "TSLA"
    assert results[0].close == Decimal("250.00")
```

---

## Деплой

### Docker Compose (production)

```yaml
# infra/docker/docker-compose.prod.yml
version: "3.9"

services:
  market_data:
    image: quantflow/market-data:${VERSION:-latest}
    restart: unless-stopped
    environment:
      - POSTGRES_HOST=${POSTGRES_HOST}
      - REDIS_URL=${REDIS_URL}
      - KAFKA_BOOTSTRAP_SERVERS=${KAFKA_BOOTSTRAP_SERVERS}
    deploy:
      replicas: 2
      resources:
        limits:
          memory: 512M
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8001/health"]
      interval: 30s
      timeout: 5s
      retries: 3

  ai_prediction_engine:
    image: quantflow/ai-engine:${VERSION:-latest}
    restart: unless-stopped
    deploy:
      replicas: 1
      resources:
        limits:
          memory: 4G
    volumes:
      - model_registry:/models

  risk_engine:
    image: quantflow/risk-engine:${VERSION:-latest}
    restart: unless-stopped
    deploy:
      replicas: 2

  execution_engine:
    image: quantflow/execution-engine:${VERSION:-latest}
    restart: unless-stopped
    deploy:
      replicas: 1  # Singleton — только один исполнитель

volumes:
  model_registry:
```

### GitHub Actions CI/CD

```yaml
# .github/workflows/ci.yml
name: CI Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: test
          POSTGRES_DB: quantflow_test
        ports: ["5432:5432"]
      redis:
        image: redis:7
        ports: ["6379:6379"]

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: pip install -e ".[dev]"

      - name: Lint (ruff)
        run: ruff check services/ shared/

      - name: Type check (mypy)
        run: mypy services/ shared/

      - name: Unit tests
        run: pytest services/ -m unit --cov=services --cov-report=xml

      - name: Integration tests
        run: pytest services/ -m integration
        env:
          POSTGRES_HOST: localhost
          REDIS_URL: redis://localhost:6379/0

      - name: Upload coverage
        uses: codecov/codecov-action@v4

  build:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      - name: Build and push Docker images
        run: |
          docker compose -f infra/docker/docker-compose.yml build
          docker compose push
```

### Makefile

```makefile
.PHONY: help infra-up infra-down dev test lint type-check build

help:
	@echo "QuantFlow - Available commands:"
	@echo "  make infra-up      Start infrastructure (Postgres, Redis, Kafka)"
	@echo "  make infra-down    Stop infrastructure"
	@echo "  make dev           Start all services in dev mode"
	@echo "  make test          Run all tests"
	@echo "  make lint          Run ruff linter"
	@echo "  make type-check    Run mypy"
	@echo "  make build         Build Docker images"
	@echo "  make db-migrate    Run Alembic migrations"
	@echo "  make seed          Seed historical data"
	@echo "  make train         Train AI models"
	@echo "  make backtest      Run backtest"

infra-up:
	docker compose -f infra/docker/docker-compose.yml up -d postgres redis kafka zookeeper

infra-down:
	docker compose -f infra/docker/docker-compose.yml down

dev:
	docker compose -f infra/docker/docker-compose.dev.yml up --build

test:
	pytest services/ -v --cov=services --cov-report=term-missing

lint:
	ruff check services/ shared/
	ruff format --check services/ shared/

type-check:
	mypy services/ shared/ --ignore-missing-imports

build:
	docker compose -f infra/docker/docker-compose.yml build

db-migrate:
	@for service in market_data news_intelligence macroeconomic ai_prediction_engine portfolio_optimizer risk_engine execution_engine; do \
		echo "Migrating $$service..."; \
		docker compose exec $$service alembic upgrade head; \
	done

seed:
	python scripts/seed_data.py --universe sp500 --years 5

train:
	python scripts/model_train.py --universe sp500 --start 2018-01-01

backtest:
	python scripts/backtest_run.py --strategy ensemble --start 2020-01-01 --end 2024-12-31
```

---

## Roadmap

| Фаза | Месяцы | Статус |
|---|---|---|
| Фаза 1: Фундамент (Data Collection) | 1–2 | 🔄 В разработке |
| Фаза 2: Аналитика (Analysis Services) | 3–4 | ⏳ Запланировано |
| Фаза 3: AI Engine (Models + Backtest) | 5–7 | ⏳ Запланировано |
| Фаза 4: Риск и Портфель | 7–9 | ⏳ Запланировано |
| Фаза 5: Исполнение + Live Trading | 9–12 | ⏳ Запланировано |

### Ближайшие задачи (v0.1)

- [ ] Market Data Service — полная реализация + тесты
- [ ] News Intelligence Service — FinBERT интеграция
- [ ] PostgreSQL схемы для всех сервисов
- [ ] Kafka topics setup + schema registry
- [ ] CI/CD pipeline (GitHub Actions)
- [ ] Docker Compose для локальной разработки

### Дальнейшие планы (v0.2+)

- [ ] Transformer (TFT) для временных рядов
- [ ] Black-Litterman с AI-взглядами
- [ ] Interactive Brokers адаптер
- [ ] Web Dashboard (Next.js + FastAPI)
- [ ] Options trading support
- [ ] Crypto markets integration

---

## Contributing

Мы приветствуем contributions! Пожалуйста, прочитайте следующие правила.

### Процесс

1. Форкните репозиторий.
2. Создайте ветку от `develop`: `git checkout -b feature/my-feature`.
3. Напишите код + тесты (coverage ≥ 80%).
4. Проверьте линтер: `make lint && make type-check`.
5. Создайте Pull Request в `develop`.

### Code Style

- Python: **ruff** (PEP 8 + расширенные правила)
- Типизация: **mypy** в strict режиме для новых модулей
- Docstrings: Google-стиль
- Тесты: **pytest** + **pytest-asyncio**
- Именование: snake_case для функций/переменных, PascalCase для классов

### Commit Convention

```
feat(market-data): add polygon.io WebSocket adapter
fix(risk-engine): correct VaR calculation for empty portfolio
test(ai-engine): add LSTM sequence building unit tests
docs(readme): update installation steps
refactor(execution): extract order validation to domain service
```

---

## Лицензия

Этот проект распространяется под лицензией **MIT**. Подробности в файле [LICENSE](LICENSE).

---

## Дисклеймер

> Данная платформа предназначена исключительно для образовательных и исследовательских целей. Алгоритмическая торговля сопряжена с существенными финансовыми рисками. Прошлые результаты бэктестов не гарантируют будущей доходности. Авторы не несут ответственности за финансовые потери, возникшие в результате использования этого программного обеспечения. Перед использованием в реальной торговле проконсультируйтесь с лицензированным финансовым советником.

---

<div align="center">

Сделано с ❤️ командой QuantFlow · [Issues](https://github.com/your-org/quantflow/issues) · [Discussions](https://github.com/your-org/quantflow/discussions)

</div>
