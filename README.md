# AI ассистент в Telegram

MVP: Telegram-ассистент, который понимает естественный язык через OpenAI API, хранит контекст в PostgreSQL, маршрутизируется через n8n и умеет:

- ставить напоминания и присылать их в Telegram;
- инициировать подключение Google OAuth для календаря и контактов;
- создавать заготовку встречи в календаре;
- вести диалог с контекстом в рамках активной темы;
- принимать поручения с интернет-поиском и сохранять уточнения в той же теме.

## Архитектура

- `n8n` принимает Telegram updates, транскрибирует голосовые при необходимости и вызывает `assistant`.
- `assistant` решает намерение через LLM, хранит пользователей, сообщения, темы, напоминания, токены интеграций и поручения.
- `postgres` хранит состояние всех пользователей.
- отдельный цикл в `assistant` проверяет наступившие напоминания и отправляет событие обратно в n8n.

## Быстрый старт

```bash
cp .env.example .env
docker compose up -d --build
```

Сервисы:

- backend: `http://localhost:8000`
- n8n: `http://localhost:5678`

## n8n webhook для входящих сообщений

Сценарий n8n должен привести Telegram update к JSON:

```json
{
  "telegram_user_id": "123456",
  "display_name": "Ivan",
  "timezone": "Europe/Moscow",
  "text": "напомни завтра в обед принять таблетку",
  "raw": {}
}
```

И отправить `POST http://assistant:8000/api/n8n/telegram-message` с заголовком:

```text
X-Assistant-Secret: значение_ASSISTANT_SECRET
```

Ответ backend содержит `text` для ответа пользователю и список `actions`, если n8n должен выполнить внешнее действие.

## Следующие шаги

1. Доделать n8n workflow: Telegram Trigger -> voice transcription -> HTTP Request в assistant -> Telegram Send Message.
2. Реализовать обмен Google OAuth `code` на refresh/access token и шифрование токенов.
3. Подключить Google Calendar API и People API в `GoogleCalendar`.
4. Реализовать web-search workflow в n8n: поиск, парсинг предложений, сравнение цены/доставки/наличия, возврат результата в чат.
5. Добавить миграции Alembic вместо `metadata.create_all` перед продакшеном.
