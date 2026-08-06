# OPTIONAL SOURCES — 03 — UI/UX Design — Gemini + Stitch

Дата: 2026-08-06. Читать только когда задача этого требует.

## Дополнительный контекст

| Документ | Когда открывать | Актуальность |
|---|---|---|
| `docs/source/02_REPOSITORY_AND_SYSTEM_ARCHITECTURE_AUDIT.md` | Source of Truth по архитектуре монорепозитория QuantFlow: состав и метрики всех модулей, фактические границы и связи трёх продуктов (Next.js-сайт, Flask-дашборд,… | в основном актуален |
| `docs/source/05_TELEGRAM_BOT_AUDIT.md` | Аудит Telegram-поверхности QuantFlow: активный бот `bot/tg/` (python-telegram-bot), legacy-модуль `bot/ui/telegram_bot.py` и Mini App — с фиксацией шести находок… | в основном актуален |
| `docs/source/07_SECURITY_PRIVACY_AND_COMPLIANCE_AUDIT.md` | Единый источник правды по безопасности, приватности и compliance проекта Quant: фиксирует фактически проверенное состояние аутентификации/авторизации, сессий, CSRF,… | в основном актуален |
| `docs/source/08_QA_TESTING_PERFORMANCE_AND_RELIABILITY_AUDIT.md` | Протокол фактически выполненных QA-проверок проекта (14 команд с дословными exit-кодами) и реестр находок Q-01…Q-07 по качеству, тестированию, производительности и… | в основном актуален |
| `docs/source/10_CURRENT_DEVELOPMENT_STATUS.md` | Единый статусный срез проекта QuantFlow: по каждому из 30 крупных компонентов (сайт, Dashboard, backend, БД, авторизация, Telegram, Mini App, торговое ядро, risk,… | в основном актуален |
| `docs/source/11_MASTER_ROADMAP.md` | Единственная актуальная дорожная карта проекта QuantFlow: 43 задачи с ID (RM-P0-001 … RM-P3-026), разложенные по 7 фазам (Phase 0 Stabilization → Phase 6 Advanced… | в основном актуален |
| `docs/source/12_AGENT_WORKSTREAMS_AND_RESPONSIBILITIES.md` | Регламент параллельной работы нескольких чатов/AI-агентов над проектом Quant: задаёт обязательные правила старта сессии, единую терминологию, карту владения файлами… | в основном актуален |
| `docs/source/14_OPEN_QUESTIONS_AND_DECISIONS.md` | Реестр открытых вопросов проекта QuantFlow, ответ на которые не выводится из кода и требует решения владельца, внешней экспертизы (юрист) или отсутствующих данных. Для… | в основном актуален |

## Вне контекста этой роли

Эти документы существуют, но по умолчанию читать их не нужно. Если задача в них
упирается — это, скорее всего, признак, что задача принадлежит другому чату.

| Документ | Чей это контекст |
|---|---|
| `docs/source/06_BACKEND_DATA_AND_INTEGRATIONS_AUDIT.md` | ENGINEERING, INFRASTRUCTURE, SECURITY, BUSINESS_ANALYST |

