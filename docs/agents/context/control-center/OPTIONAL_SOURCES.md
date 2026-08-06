# OPTIONAL SOURCES — 01 — Control Center — Project Manager & Business Analyst

Дата: 2026-08-06. Читать только когда задача этого требует.

## Дополнительный контекст

| Документ | Когда открывать | Актуальность |
|---|---|---|
| `docs/source/02_REPOSITORY_AND_SYSTEM_ARCHITECTURE_AUDIT.md` | Source of Truth по архитектуре монорепозитория QuantFlow: состав и метрики всех модулей, фактические границы и связи трёх продуктов (Next.js-сайт, Flask-дашборд,… | в основном актуален |
| `docs/source/03_WEBSITE_AUDIT.md` | Полный аудит маркетингового сайта `website/` (Next.js 15 + next-intl, локали /ru и /en): карта маршрутов, структура лендинга, адаптивность на 5 разрешениях,… | в основном актуален |
| `docs/source/04_DASHBOARD_AUDIT.md` | Источник истины по операторскому дашборду QuantFlow (`bot/ui/`): полная карта 12 экранов SPA и API-поверхности (42 маршрута `/api/v2`, 14 legacy `/api/*`, 30… | в основном актуален |
| `docs/source/05_TELEGRAM_BOT_AUDIT.md` | Аудит Telegram-поверхности QuantFlow: активный бот `bot/tg/` (python-telegram-bot), legacy-модуль `bot/ui/telegram_bot.py` и Mini App — с фиксацией шести находок… | в основном актуален |
| `docs/source/06_BACKEND_DATA_AND_INTEGRATIONS_AUDIT.md` | Source-of-truth аудит серверной части Quant: модель данных и схема БД (SCHEMA_VERSION = 4), механизм миграций, все внешние интеграции (Tinkoff, Finam, Bybit, MOEX ISS,… | в основном актуален |
| `docs/source/07_SECURITY_PRIVACY_AND_COMPLIANCE_AUDIT.md` | Единый источник правды по безопасности, приватности и compliance проекта Quant: фиксирует фактически проверенное состояние аутентификации/авторизации, сессий, CSRF,… | в основном актуален |
| `docs/source/08_QA_TESTING_PERFORMANCE_AND_RELIABILITY_AUDIT.md` | Протокол фактически выполненных QA-проверок проекта (14 команд с дословными exit-кодами) и реестр находок Q-01…Q-07 по качеству, тестированию, производительности и… | в основном актуален |
| `docs/source/09_PRODUCT_UX_MARKETING_AND_MONETIZATION_AUDIT.md` | Продуктовый аудит Quant: аудитория и сегментация, позиционирование и УТП, полная воронка от лендинга до activation, состояние монетизации, retention и готовность к… | в основном актуален |

## Вне контекста этой роли

Эти документы существуют, но по умолчанию читать их не нужно. Если задача в них
упирается — это, скорее всего, признак, что задача принадлежит другому чату.

| Документ | Чей это контекст |
|---|---|
| — | — |

