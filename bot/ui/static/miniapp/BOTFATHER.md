# Подключение QuantFlow Mini App в BotFather

## Требования

- Telegram-бот уже создан и запущен (`bot/tg/bot.py`)
- Dashboard доступен по **HTTPS** (обязательно для Mini App)
- Домен с валидным SSL-сертификатом

> Локально (`http://127.0.0.1:5001`) Mini App работает в браузере, но **не** внутри Telegram — нужен публичный HTTPS URL.

---

## Шаг 1 — Опубликовать Dashboard

### Вариант A: Production-сервер

```bash
cd bot && python3 ui/dashboard.py
# Dashboard на порту 5001 (или за nginx/caddy)
```

URL Mini App:
```
https://YOUR-DOMAIN/static/miniapp/index.html
```

### Вариант B: Туннель для разработки (ngrok / cloudflared)

```bash
ngrok http 5001
```

Получите URL вида `https://abc123.ngrok.io` → Mini App:
```
https://abc123.ngrok.io/static/miniapp/index.html
```

---

## Шаг 2 — Настроить BotFather

1. Откройте [@BotFather](https://t.me/BotFather) в Telegram
2. Отправьте `/mybots`
3. Выберите вашего бота → **Bot Settings**
4. **Menu Button** → **Configure menu button**
5. Укажите:
   - **Button text:** `QuantFlow` или `Открыть терминал`
   - **Web App URL:** `https://YOUR-DOMAIN/static/miniapp/index.html`

### Альтернатива — команда с Web App

В BotFather:
```
/setcommands
```

Добавьте:
```
trade - Открыть торговый терминал
game - CRYPTONITE игра
```

> Для кнопки Web App в коде бота (без изменения backend сейчас) используйте Menu Button в BotFather — это достаточно.

---

## Шаг 3 — Проверка

1. Откройте бота в Telegram
2. Нажмите кнопку меню (≡) внизу → должна открыться Mini App
3. Проверьте вкладки:
   - **Trade** — баланс, 8 paper-позиций, сигналы
   - **CRYPTONITE** — игра, daily reward, leaderboard

---

## Шаг 4 — CORS и безопасность

Mini App загружает API с того же домена (`/api/platform/*`). Убедитесь:

- Dashboard и Mini App на **одном домене**
- `X-Dashboard-Api-Key` не требуется для GET с localhost; на production настройте при необходимости

---

## Шаг 5 — Добавить кнопку в бота (опционально, требует правку tg/)

Чтобы бот отправлял inline-кнопку «Открыть Mini App», в handler добавьте:

```python
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

keyboard = InlineKeyboardMarkup([[
    InlineKeyboardButton(
        "📊 QuantFlow Terminal",
        web_app=WebAppInfo(url="https://YOUR-DOMAIN/static/miniapp/index.html")
    )
]])
```

> Это изменение backend (`bot/tg/`) — выполняйте отдельно при необходимости.

---

## Troubleshooting

| Проблема | Решение |
|----------|---------|
| Белый экран в Telegram | Проверьте HTTPS и доступность URL |
| Нет позиций | Paper account: `/api/platform/paper/account` |
| API 403 | Добавьте `X-Dashboard-Api-Key` в Settings Dashboard |
| Игра не сохраняется | localStorage — нормально, данные на устройстве |

---

## URL-ы проекта

| Ресурс | Путь |
|--------|------|
| Dashboard | `https://DOMAIN/` |
| Mini App | `https://DOMAIN/static/miniapp/index.html` |
| SSE Stream | `https://DOMAIN/api/platform/stream` |