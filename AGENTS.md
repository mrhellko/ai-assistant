# Инструкции для Codex

## Общение

- Всегда отвечай пользователю на русском языке, если пользователь явно не попросит другой язык.
- Перед изменениями в коде сначала быстро прочитай релевантную документацию проекта.

## Инженерные правила

- Не добавляй локальное NLP через списки ключевых слов, словари фраз или регулярки
  для распознавания намерений, местоимений и пользовательских смыслов. Для таких
  задач используй intent-manager, структурированные данные, отдельный LLM-resolver
  или явные доменные сущности. Исключение - простая техническая валидация уже
  структурированных callback/data payload.
- После выполнения работы по добавлению нового функционала проводи техническое и
  аналитическое ревью по skill `skills/project-review/SKILL.md`: проверь код,
  соответствие `docs/PLAN.md`, проектные нормы, документацию, тесты и
  эксплуатационные риски.
- После review-прохода для изменений, которые меняют поведение приложения,
  синхронизируй документацию и план по skill `skills/project-doc-sync/SKILL.md`.

## Где искать контекст

- `README.md` - быстрый старт, docker compose, Telegram webhook, публичный URL.
- `docs/PLAN.md` - актуальный план разработки и статус этапов.
- `docs/WEB_SEARCH.md` - отдельная документация по web-search поведению,
  контексту и пользовательской настройке `location`.
- `docs/INTENT_MANAGER.md` - контракт intent-manager, список intent и правила контекста.
- `docs/MEMORY.md` - будущий модуль долговременной памяти, модель knowledge graph и поиск.
- `docs/REMINDERS.md` - подробная документация процесса напоминаний.
- `services/assistant/app/api/telegram.py` - Telegram webhook, callback-кнопки.
- `services/assistant/app/services/assistant.py` - основной сценарий обработки сообщений.
- `services/assistant/app/agents/intent_manager.py` - запросы к LLM и схема intent routing.
- `services/assistant/app/scheduler/reminders.py` - цикл отправки напоминаний.
- `services/assistant/app/integrations/telegram.py` - Telegram Bot API client.

## Текущее состояние проекта

Проект - Telegram AI assistant на FastAPI, PostgreSQL, Docker Compose и Caddy.

Реализовано:

- текстовый Telegram loop через webhook;
- создание пользователей, тем и сообщений;
- LLM intent-manager через OpenAI Responses API;
- напоминания естественным языком;
- подтверждение напоминания с человекочитаемым временем;
- отправка напоминаний через Telegram Bot API;
- кнопки `ОК` и `Перенести на 5 минут`;
- защита от duplicate callback при переносе;
- Caddy reverse proxy с HTTPS;
- документация процесса напоминаний.
- документация intent-manager.
- зафиксирована концепция будущего Memory Module.

Текущая модель по умолчанию задается в `.env.example`:

```env
OPENAI_MODEL=gpt-4.1-mini
```

## Команды

Запуск/деплой:

```bash
docker compose up -d --build
```

Проверка health:

```bash
curl -fsS https://order.mrhellko.ru/health
```

Проверка Python-кода:

```bash
python3 -m compileall services/assistant/app
docker compose exec -T assistant ruff check app
```

Проверка форматирования только измененных файлов предпочтительнее, потому что весь старый код может быть не приведен к formatter сразу:

```bash
docker compose exec -T assistant ruff format --check app/path/to/file.py
```

## Git

- Перед коммитом проверяй `git status --short` и `git diff --check`.
- Не коммить реальные `.env`, токены, cookies, OAuth payload и дампы БД.
- Глобальный git user уже настроен:
  - `user.name = mrhellko`
  - `user.email = mrhellko@gmail.com`

## Ближайшие ориентиры

Следуй `docs/PLAN.md`. На момент создания этого файла ближайшие крупные направления:

1. голосовая транскрибация;
2. Google OAuth и создание календарных событий;
3. web-search поручения;
4. production deployment guide и cold start проверка;
5. backup PostgreSQL;
6. миграции, тесты и hardening;
7. Memory Module для долговременных пользовательских знаний.
