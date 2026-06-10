# AI ассистент в Telegram

MVP: Telegram-ассистент, который понимает естественный язык через OpenAI API, хранит контекст в PostgreSQL и умеет:

- ставить напоминания и присылать их в Telegram;
- инициировать подключение Google OAuth для календаря и контактов;
- создавать заготовку встречи в календаре;
- вести диалог с контекстом в рамках активной темы;
- принимать поручения с интернет-поиском и сохранять уточнения в той же теме.

## Архитектура

- `assistant` принимает Telegram webhook, отвечает через Telegram Bot API и решает намерение через LLM intent-manager.
- `assistant` хранит пользователей, сообщения, темы, напоминания, токены интеграций и поручения.
- `postgres` хранит состояние всех пользователей.
- отдельный цикл в `assistant` проверяет наступившие напоминания и отправляет их в Telegram.

## Быстрый старт

```bash
cp .env.example .env
docker compose up -d --build
```

Сервисы:

- public HTTPS: `https://order.mrhellko.ru`
- backend внутри Docker: `assistant:8000`

## Telegram webhook

После запуска сервиса нужно установить webhook Telegram:

```bash
curl -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook" \
  -d "url=$ASSISTANT_PUBLIC_BASE_URL/api/telegram/webhook" \
  -d "secret_token=$TELEGRAM_WEBHOOK_SECRET"
```

Telegram будет отправлять update напрямую в backend, backend сам отправит ответ пользователю через Bot API.

Для production сервер должен принимать входящие TCP-порты `80` и `443`. Caddy в `docker-compose.yml` автоматически выпускает HTTPS-сертификат Let's Encrypt для домена из `ASSISTANT_DOMAIN`.

## Следующие шаги

Основной рабочий план хранится в [docs/PLAN.md](docs/PLAN.md).

Контракт распознавания намерений описан в [docs/INTENT_MANAGER.md](docs/INTENT_MANAGER.md).

Концепция будущей долговременной памяти описана в [docs/MEMORY.md](docs/MEMORY.md).
