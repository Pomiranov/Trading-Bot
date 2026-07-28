# QuantFlow Operational Dashboard — Implementation Plan

**Дата:** 2026-07-29 · **Репозиторий:** `/Users/danila/Downloads/Trading-Bot-merge-learning-nik`
**Ветка:** `quant-site-approved-reference-redesign` · **HEAD на момент старта:** `80ec121`

Этот документ — рабочий план реализации, а не аудит. Источник ТЗ:
`design/DASHBOARD_APPROVED_REFERENCE_AUDIT.md`. Каждое утверждение аудита перепроверено
по текущему коду и по живой БД (только чтение) перед тем, как попасть в план.

---

## 0. Расхождение путей (зафиксировано, не исправляется автоматически)

`CLAUDE.md` объявляет канонической директорию `/Users/danila/Documents/GitHub/Trading-Bot/`
и активной ветку `merge-learning-nik`. Фактически ветка `quant-site-approved-reference-redesign`,
директория `website/`, approved reference и вся траектория редизайна находятся в
`~/Downloads/Trading-Bot-merge-learning-nik`. Работа выполняется здесь — там, откуда запущен
Claude Code и где реально лежит работа. Расхождение выносится в итоговый отчёт как решение
владельца продукта (D-01 аудита); `CLAUDE.md` в рамках этой задачи не перезаписывается,
чтобы не создавать второй конфликтующий источник истины.

## 0.1 Неприкосновенные изменения пользователя

На старте в рабочем дереве уже были:

```
 M .gitignore                  (+8: /*.mp4, .playwright-mcp/)
 M bot/qf_platform/schema.py   (+5/−2: перенос двух CREATE INDEX после ALTER TABLE)
?? .coverage
?? approved-stitch-reference.jpg
?? design/DASHBOARD_APPROVED_REFERENCE_AUDIT.md
```

`schema.py` содержит **именно тот** фикс ordering-дефекта, который требует §8 ТЗ. Он сохранён
как есть и войдёт в первый коммит вместе со остальными изменениями схемы. Остальные
незакоммиченные файлы не трогаются.

---

## 1. Текущая архитектура (проверено по коду)

```
bot/ui/dashboard.py            751  Flask app на module scope; при импорте:
                                    create_engine(pool_size=2, max_overflow=3) → :65
                                    ensure_platform_schema(_engine)            → :70   ← DDL при импорте
                                    seed_knowledge_hypotheses(_engine)         → :77   ← запись при импорте
                                    paper_engine.start()                       → :89   ← торговый цикл при импорте
                                    _sharpe()/_max_drawdown() в route-модуле   → :109-130
bot/ui/api/platform_routes.py   676  30 routes, 17 inline SQL, 4 «GET, который пишет»
bot/qf_platform/services/**          derivations частично; AVG(ABS(pnl_pct)) в portfolio_service
bot/qf_platform/repositories/**      2 репозитория, остальной SQL живёт выше
bot/security/dashboard_auth.py   99  один before_request, IP + опциональный API-key
bot/ui/templates/dashboard.html 911  статичная оболочка, 18 Jinja-выражений — все url_for
bot/ui/static/**              ~5900  vanilla JS: свой store/api/sync/render, 2 CDN chart-библиотеки
```

Ключевой факт, определяющий стоимость: **Jinja не интерполирует ни одного данных**.
`index()` — это `render_template("dashboard.html")` без контекста. Dashboard уже SPA.
Поэтому выбрана архитектура **Flask API + client-rendered SPA в том же приложении**
(Option A аудита), как и требует §5 ТЗ. Никакого Next.js, никакого слияния с сайтом.

---

## 2. Проверенные дефекты (перепроверка на живой БД, read-only)

Состояние БД на 2026-07-28 22:42 UTC:

| Факт | Значение |
|---|---|
| `now()` | `2026-07-28 22:42 UTC` |
| `max(candles.time)` | `2026-06-26` → **возраст данных 32 дня** |
| `candles` | 1 334 строк |
| `trades` | **2** |
| `paper_trades` | **35** |
| `paper_positions` | 1 |
| `equity_snapshots` | **16 123 строк / 44 различных значения equity** |
| `trading_signals` | 8 |
| `skipped_signals` / `forward_state` / `system_events` | **0 / 0 / 0** |
| `audit_events` | 12 (все `api.auth.denied`) |
| `belief_system` / `hypotheses` | 8 / **0** |
| `paper_accounts` | `balance=7 626 545,68`, `available=12 359 136,94`, `initial=10 000 000` |

### P0 — блокеры корректности

| # | Дефект | Точное место | Исправление |
|---|---|---|---|
| D1 | `/api/equity` при пустых closed trades падает в `_candle_equity()` — цена SBER, нормированная на 1 000 000, выдаётся как equity портфеля | `bot/ui/dashboard.py:197-211`, `:574-586` | Новый `EquityService` над `equity_snapshots`; candle-fallback удалён; при отсутствии истории — честный `EMPTY_NO_HISTORY` |
| D2 | Каждая цена — из свечи 32-дневной давности, UI не показывает возраст | `paper_trading_service.py:26-37`, `dashboard.py:250-257` | `MarketDataRepository.quote_freshness()`; `source_as_of` / `data_age_seconds` в meta каждого price-derived ответа; per-cell stale-маркер |
| D3 | `avg_profit_pct = AVG(ABS(pnl_pct))` — убыточный счёт показывает `+16,07 %` | `portfolio_service.py:207` и `:212` | Signed mean `AVG(pnl_pct)` + отдельный `avg_abs_move_pct`; оба с `n` |
| D4 | `max_drawdown` — одно имя, две единицы: `_compute_max_drawdown` возвращает долю (0,2373), UI печатает её как проценты → «−0,24 %» вместо «−23,73 %» | `analytics_service.py:258-280`, `:200` | `max_drawdown_pct` (−23,73) и `max_drawdown_abs` (−2 373 454,32) как отдельные поля; `units` в meta |
| D5 | Серия equity сэмплируется частотой поллинга: 2 987 интервалов ровно по 12 000 мс = `POLL_MS` | `paper_trading_service.py:73` внутри `refresh_positions` | Снапшоты пишет только движок; `EquityService` ресемплит по времени, а не по числу строк |
| D6 | «История Paper Trades» пуста при 35 строках — envelope mismatch | `platform_routes.py:300` отдаёт голый список | v2-контракт `{data:{trades:[…]},meta:{…}}` + contract-тест «N строк в БД → N строк в ответе» |
| D7 | `is_sandbox` не фильтруется нигде вне DDL | grep по `bot/ui/**`, `bot/qf_platform/**` | Enum `Environment{SANDBOX,FORWARD,BACKTEST,LIVE,UNKNOWN}`; в каждом DTO и каждой строке таблицы; неизвестное → `UNKNOWN` как ошибка конфигурации, никогда не sandbox |
| D8 | GET, которые пишут | `paper/account`→`refresh_positions`→INSERT `equity_snapshots`+UPDATE; `portfolio`, `overview` — то же; `signals`→`generate_live_signals(persist=True)` при пустой выборке | Все v2 GET read-only; в `PaperTradingService` разделены `refresh_positions` (write) и `compute_positions` (read-only) |
| D9 | DDL при импорте модуля | `dashboard.py:70` → `bootstrap.py:16-30`, одна транзакция на весь скрипт | `ensure_platform_schema` требует явного `allow_ddl=True`; отдельная команда `python -m qf_platform.migrate`; каждое выражение в своей транзакции с логом номера |
| D10 | Частичный sync помечается как «live» | `core/sync.js` `allSettled` → безусловный `syncStatus:'live'` | Новый sync-слой: freshness на каждый slice, глобальный статус = худший из slice |

### P0 — безопасность

| # | Дефект | Исправление |
|---|---|---|
| S1 | Авторизация по IP; при shipped defaults ни один route не требует секрета | Серверные сессии + Argon2id-хеш пароля (`werkzeug.security` scrypt как fallback, если argon2-cffi недоступен), `HttpOnly`/`SameSite=Strict`/`Secure` в prod, ротация id после входа, rate limit, generic-ошибки |
| S2 | CSRF нет нигде | Double-submit токен + `X-CSRF-Token` на всех мутациях; mutating GET запрещены |
| S3 | `bot/auth/**` — мёртвый код, документированный как живой | Не используется; заменён на `bot/security/session_auth.py`. Удаление отложено (D-09) — фиксируется в отчёте |
| S4 | Нет audit trail действий | `audit_record` на каждой мутации: actor, role, action, target, environment, before/after, reason, outcome, correlation id, idempotency key |
| S5 | 31 unescaped `innerHTML`, ticker в `onclick="…"` | Frontend переписан на `textContent`/`createElement`; `innerHTML` нет ни одного; inline-обработчиков нет ни одного; CSP без `unsafe-inline` для скриптов |

---

## 3. Последовательность изменений

| Этап | Содержание | Файлы |
|---|---|---|
| **0** | Контракты, freshness, environment, миграции, read-only режим | `qf_platform/contracts.py`, `environment.py`, `migrate.py`, `bootstrap.py`, `schema.py` |
| **1** | Репозитории (весь SQL) и сервисы (все derivations) | `repositories/{market,equity,trades,positions,strategies,events,risk,audit}_repository.py`, `services/{environment,equity,metrics,faults,positions,trades,signals,strategies,risk,health,events}_service.py` |
| **2** | Безопасность: сессии, роли, CSRF, error envelope, audit | `security/{session_auth,csrf,errors,readonly,permissions}.py` |
| **3** | `/api/v2` — тонкие routes над сервисами | `ui/api/v2/**` |
| **4** | Дизайн-система: Geist локально, токены, lint | `ui/static/fonts/**`, `ui/static/css/**`, `ui/static/check-dashboard-tokens.mjs` |
| **5** | Shell, роутер, форматтер, store/sync, DataTable, charts, диалоги | `ui/static/app/**`, `templates/{shell,login}.html` |
| **6** | 12 экранов | `ui/static/app/views/**` |
| **7** | Тесты + runtime QA + документация | `tests/dashboard_tests/**`, `docs/DASHBOARD_OPERATIONS.md` |

Порядок обязателен: сначала правда данных и замки, затем бренд. Красивый дашборд,
показывающий +16 % на убыточном счёте, опаснее некрасивого.

---

## 4. Дизайн-решения

* **Токены** — dashboard-owned копия значений сайта (`bot/ui/static/css/tokens.css`).
  `website/**` не изменяется и не становится зависимостью сборки dashboard. Синхронизацию
  проверяет отдельный dashboard-side скрипт, который читает значения сайта только на чтение.
* **Палитра** — фон/поверхности/текст/границы/success/danger/neutral прямо из сайта;
  `--qf-warning: #d9c187` — единственное новое значение. Orange, purple, cyan-as-ink удалены
  полностью. Cold blue живёт только на sign-in и в empty-state как stroke ≤0.28α.
* **Типографика** — Geist + Geist Mono, self-hosted (4 woff2, latin + cyrillic), Orbitron удалён,
  runtime-запросов к Google Fonts нет. 6 ролей, `tabular-nums lining` на всех числах.
* **Геометрия** — радиусы 4/8/12/16/20/24/full, правило `inner = outer − 4`; ровно 3 тени;
  glass только для modal/popover/tooltip.
* **Motion** — `cubic-bezier(.16,1,.3,1)`, 150/220/400 мс. Ни одной бесконечной анимации.
  `prefers-reduced-motion` заменяет движение статическим эквивалентом, а не нулевой длительностью.
* **Charts** — обе CDN-библиотеки удалены. Собственные SVG-рендереры (sparkline, line, underwater,
  signed bars, step, histogram, latency) — ~10 КБ, без внешних зависимостей, с `ResizeObserver`,
  disposal, textual summary и data-table альтернативой.

---

## 5. Риски и их снятие

| Риск | Снятие |
|---|---|
| Отключение DDL при импорте ломает свежий деплой | `python -m qf_platform.migrate --check` в старте; при незамигрированной схеме приложение поднимается, но отдаёт `SCHEMA_OUT_OF_DATE` вместо тихих 500 |
| Убирание `paper_engine.start()` из импорта остановит песочницу | Автостарт вынесен под `QF_DASHBOARD_AUTOSTART_ENGINE=1` (по умолчанию выключен), плюс отдельная operator-кнопка с подтверждением и audit |
| Полная замена frontend ломает Telegram Mini App | Mini App вынесен на собственный route `/miniapp` со своим CSS-скоупом; из operational-оболочки его стили и скрипты больше не загружаются |
| Старый `/api/*` используется Mini App и ботом | Legacy-роуты сохранены, но GET сделаны read-only; v2 — новый параллельный контракт |
| Незакоммиченные изменения пользователя | Не трогаются; `.gitignore` и `schema.py` входят в коммит как есть |
| Нет `argon2-cffi` в окружении | Пароль хешируется через `argon2id`, если библиотека есть, иначе `scrypt` (Werkzeug, встроенный); алгоритм записан в самом хеше, миграция прозрачна |

**Rollback:** каждый этап — отдельный коммит с одной зоной ответственности.
`git revert <sha>` откатывает этап целиком. Frontend полностью заменён новыми файлами;
старые (`design-system.css`, `style.css`, `app.js`, `platform.js`, `charts.js`,
`components.js`, `views/render.js`, `views/learning.js`, `core/*`) удалены в отдельном коммите,
поэтому откат одного revert'а возвращает прежнюю оболочку целиком.

---

## 6. Тестовая стратегия

* **Контракты** — на каждый v2 endpoint: наличие `meta.as_of`/`environment`/`units`,
  `n` у каждого агрегата, структура error envelope.
* **Корректность** — signed average на полностью убыточном наборе; drawdown pct/abs
  на нулевой истории, монотонном росте, падении 23,7 %, восстановлении; equity из
  `equity_snapshots`, никогда из candles.
* **Read-only** — каждый v2 GET прогоняется на подменённом engine, который падает
  при любом `INSERT/UPDATE/DELETE`.
* **Безопасность** — 401 без сессии, 403 без роли, 403 без CSRF, generic-ошибка входа,
  rate limit, ротация сессии, отсутствие секретов в ответе.
* **Миграции** — прогон на «legacy-like» схеме `trades(22 колонки)`; проверка, что импорт
  модуля не выполняет DDL.
* **Frontend** — formatters (ru-RU, NBSP, U+2212), store subscribe/unsubscribe, роутер,
  per-slice freshness, partial sync, сортировка/фильтрация таблицы, рендер XSS-payload.
* **Runtime QA** — запуск в read-only режиме, обход всех экранов, скриншоты
  1680×1050 / 1440×900 / 1280×800 / 1024×768 / 768×1024 / 390×844 / 844×390.

---

## 7. Объективно отсутствующие данные (не выдумываются)

| Чего нет | Следствие в UI |
|---|---|
| `pnl_r` в `paper_trades` | Колонка PnL R показывается только для `trades`, где поле есть; иначе `н/д` |
| `belief_history` | График истории уверенности не строится; показывается «нет истории» |
| `frozen`-флаг стратегии | Состояние выводится из `updated_at` + `total_trades`; «Заморожена» не изобретается |
| Telegram delivery status | Раздел не добавляется (нет entity) |
| Orders | Раздел не добавляется (нет entity) |
| `quote_ts` на позиции | Возраст котировки берётся из `max(candles.time)` по тикеру — это реальный источник |
| Дневной лимит убытка в ₽ | Есть только процент в конфиге → показывается процент и производная сумма, помеченная как производная |
| Латентность API | Замеряется самим приложением (in-process гистограмма), а не выдумывается |
