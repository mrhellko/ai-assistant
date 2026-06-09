# n8n workflows

Здесь стоит хранить экспортированные JSON workflow из n8n.

Минимальный набор:

- `telegram-inbound.json`: Telegram Trigger -> подготовка payload -> HTTP Request в assistant -> Telegram Send Message.
- `assistant-outbound.json`: Webhook `assistant-outbound` -> Telegram Send Message.
- `web-search-task.json`: Webhook/Execute Workflow -> поиск предложений -> нормализация результата -> отправка в assistant или Telegram.

