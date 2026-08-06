# QuantFlow Operational Dashboard — эксплуатация

Как запустить, миграцировать, проверить и безопасно посмотреть на живые данные.

---

## 1. Запуск

### Обычный запуск

```bash
python3 bot/ui/dashboard.py            # http://127.0.0.1:5001
```

Импорт модуля больше не выполняет DDL, не сеет гипотезы и не запускает торговый
движок. Всё это происходит только внутри `create_app()`, и движок — только по явному
разрешению.

### Режим только для чтения — для QA и для просмотра production

```bash
QF_DASHBOARD_READ_ONLY=1 python3 bot/ui/dashboard.py
```

В этом режиме:

* все мутирующие endpoints возвращают `READ_ONLY_MODE` до вызова сервиса;
* потоки движка не запускаются;
* миграции не выполняются;
* брокеру не отправляется ни одной торговой команды;
* **на уровне соединения SQLAlchemy** запись отклоняется, поэтому ошибка в сервисе
  не может превратиться в запись.

Разрешены записи только в инфраструктурные таблицы, иначе режим был бы
неиспользуемым (нельзя было бы войти): `dashboard_sessions`,
`dashboard_login_attempts`, `dashboard_users` (счётчик блокировок и `last_login_at`),
`audit_events`, `system_events`, `action_idempotency`. Ни одной доменной таблицы в
этом списке нет.

### Автостарт движка

По умолчанию выключен — импорт модуля больше не начинает торговать.

```bash
QF_DASHBOARD_AUTOSTART_ENGINE=1 python3 bot/ui/dashboard.py
```

Либо кнопка оператора в environment band (роль `operator`, с подтверждением,
причиной и записью в аудит).

---

## 2. Миграции

Единственный авторитетный путь. `bot/qf_platform/schema.py` — данные,
`qf_platform.migrate` — единственный исполнитель.

```bash
python -m qf_platform.migrate --check      # только отчёт, ничего не пишет
python -m qf_platform.migrate              # применить (спросит подтверждение)
python -m qf_platform.migrate --yes        # применить без вопросов (CI/деплой)
```

Каждое выражение выполняется в собственной транзакции. Если одно падает, остальные
применяются, а в отчёте указан его номер и первая строка. Раньше весь скрипт шёл
одной транзакцией: `CREATE INDEX` по колонке, которую добавлял *следующий*
`ALTER TABLE`, откатывал все сорок ALTER'ов — молча, после чего четыре endpoint'а
навсегда отдавали 500 при чистой консоли браузера.

`--check` безопасен против production: он делает только SELECT по системному
каталогу и сравнивает фактические колонки со списком `REQUIRED_COLUMNS`, а не
доверяет журналу версий (частично откатившаяся миграция оставляет журнал
выглядящим здоровым).

**Перед применением против production сделайте резервную копию:**

```bash
docker exec trading_db pg_dump -U trader -d trading_bot --clean --if-exists > backup.sql
```

Веб-процесс при старте выполняет только проверку. Если схема устарела, дашборд
поднимется, но API вернёт `SCHEMA_OUT_OF_DATE` вместо случайных 500 — и fault region
покажет это первой строкой.

---

## 3. Операторы и права

Пароля по умолчанию нет ни в коде, ни в конфигурации.

```bash
python -m qf_platform.migrate --create-user НАМЕ --role administrator
python -m qf_platform.migrate --create-user observer1 --role observer
python -m qf_platform.migrate --create-user trader1 --role operator --trading-authorized
```

Пароль запрашивается интерактивно (или через `QF_NEW_USER_PASSWORD` для CI),
хешируется Argon2id при наличии `argon2-cffi`, иначе scrypt. Алгоритм записан в
самом хеше, поэтому переход прозрачен: хеш обновляется при следующем входе.

Для первого запуска на чистом деплое:

```bash
QF_DASHBOARD_BOOTSTRAP_USER=operator \
QF_DASHBOARD_BOOTSTRAP_PASSWORD='…' \
python3 bot/ui/dashboard.py
```

Переменная читается один раз, хешируется и **не сохраняется**. Уберите её после
первого входа и смените пароль.

### Роли

| Роль | Может |
|---|---|
| `observer` | читать всё, не менять ничего |
| `operator` | пауза/запуск движка, переподключение, подтверждение инцидента, бэктест |
| `administrator` | всё выше + учётные данные, лимиты, стратегии, журнал аудита |

`trading_authorized` — отдельный флаг, не роль. Администратор, управляющий
конфигурацией, не может закрыть позицию только в силу роли.

Торговые действия дополнительно закрыты рубильником, по умолчанию выключенным:

```bash
QF_DASHBOARD_ALLOW_TRADING_ACTIONS=1   # исполнение сигнала, закрытие позиции
QF_DASHBOARD_ALLOW_LIVE=1              # переключение в live — отдельно
```

---

## 4. Переменные окружения

| Переменная | По умолчанию | Значение |
|---|---|---|
| `QF_DASHBOARD_READ_ONLY` | `0` | режим только для чтения |
| `QF_DASHBOARD_AUTOSTART_ENGINE` | `0` | автостарт торгового движка |
| `QF_DASHBOARD_ALLOW_TRADING_ACTIONS` | `0` | торговый уровень действий |
| `QF_DASHBOARD_ALLOW_LIVE` | `0` | переключение в live |
| `QF_ALLOW_STARTUP_DDL` | `0` | миграция при старте (не рекомендуется) |
| `QF_HTTPS` | `0` | HSTS + `Secure` на cookie |
| `QF_INSECURE_COOKIES` | `0` | отключить `Secure` (только localhost) |
| `QF_SESSION_TTL_SECONDS` | `28800` | срок сессии, скользящий |
| `QF_LOGIN_MAX_FAILURES` | `5` | порог rate limit за окно |
| `QF_LOGIN_WINDOW_SECONDS` | `300` | окно rate limit |
| `QF_ACCOUNT_LOCK_AFTER` | `10` | блокировка аккаунта после N неудач |
| `QF_ACCOUNT_LOCK_MINUTES` | `15` | длительность блокировки |
| `QF_DB_POOL_SIZE` | `5` | размер пула (было 2) |
| `QF_DB_MAX_OVERFLOW` | `10` | overflow пула (было 3) |
| `QF_STATIC_MAX_AGE` | `2592000` | кеш статики, 30 дней |
| `QF_DASHBOARD_DEBUG` | `0` | отладка; запрещена при host ≠ loopback |

---

## 5. Проверки

```bash
# Python
python3 -m compileall bot
python3 -m pytest tests -q

# Только тесты дашборда. Аутентифицированные контрактные тесты требуют
# учётных данных, иначе аккуратно скипаются.
QF_TEST_USER=operator QF_TEST_PASSWORD='…' python3 -m pytest tests/dashboard_tests -q

# Frontend
node --test bot/ui/static/app/format.test.mjs
node bot/ui/static/check-dashboard-tokens.mjs

# Сайт (read-only для этой задачи; должен остаться зелёным)
cd website && npm run check
```

`check-dashboard-tokens.mjs` делает две вещи: запрещает raw-цвета, снятые оттенки,
произвольные размеры/радиусы/тени, бесконечные анимации, `innerHTML` и inline-обработчики
— и **проверяет происхождение**: читает `website/src/styles/tokens/color.css` (только на
чтение) и падает, если скопированное значение разошлось с источником.

---

## 6. Обслуживание

`equity_snapshots` вырос до 16 123 строк с 44 различными значениями, потому что
четыре GET-обработчика вставляли по строке на каждый 12-секундный опрос. Записи
убраны; накопленное чистится явным действием администратора:

```
POST /api/v2/maintenance/prune-equity
{"keep_days": 365, "full_resolution_days": 7, "reason": "retention"}
```

Полное разрешение за последние `full_resolution_days`, одна точка в день дальше,
ничего за пределами `keep_days`. Это не запускается по просмотру страницы.

---

## 7. Диагностика

| Симптом | Что смотреть |
|---|---|
| `SCHEMA_OUT_OF_DATE` | `python -m qf_platform.migrate --check` |
| Вход не проходит, «Оператор не создан» | `--create-user` |
| Вход возвращает 429 | сработал rate limit; `QF_LOGIN_WINDOW_SECONDS` |
| Все панели «Только чтение» | `QF_DASHBOARD_READ_ONLY=1` |
| Кнопки действий выключены | наведите курсор — в подсказке написана причина |
| Данные «32 дн назад» | загрузчик свечей; `/api/v2/market/coverage` |
| Ошибка в UI с ID | найдите этот ID в `/events` (colonка Correlation ID) |

В браузере доступна диагностика клиента:

```js
window.__qf.diagnostics()
// { requestsPerMinute, listeners, charts, slices, tasks }
```

`listeners` и `charts` не должны расти при переключении экранов — это две
канарейки на утечки.

---

## 8. Что осталось незакрытым

Смотрите раздел «Remaining blockers» в отчёте по редизайну. Кратко: нет таблицы
`belief_history` (история уверенности восстанавливается по сделкам и помечена как
таковая), нет `pnl_r` в `paper_trades` (колонка показывает `н/д`, не `0R`), нет
статуса доставки Telegram и нет сущности Orders — поэтому соответствующих разделов
в навигации нет.
