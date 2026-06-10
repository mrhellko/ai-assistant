# Напоминания

Документ описывает текущий процесс создания, хранения, отправки и переноса напоминаний.

## Когда вызывается процесс напоминаний

Процесс создания начинается с любого текстового Telegram-сообщения, которое
intent-manager классифицирует как `intent="reminder_create"`.

Типичные примеры:

- "напомни через минуту включить чайник";
- "завтра в обед принять таблетку";
- "во вторник в 16:30 сводить ребенка в поликлинику";
- "через 2 часа проверить доставку".

Если пользователь прислал voice message, сейчас напоминание не создается: backend отвечает, что голосовые сообщения пока не подключены.

Список будущих напоминаний и история напоминаний также проходят через
intent-manager. В backend больше нет локального списка шаблонных фраз вроде
"покажи уведомления".

## Поток создания

1. Telegram отправляет update в `POST /api/telegram/webhook`.
2. `app.api.telegram.telegram_webhook` извлекает `chat_id`, `sender`, `text` и собирает `IncomingTelegramMessage`.
3. `AssistantService.handle_telegram_message`:
   - создает или находит пользователя;
   - находит активную тему;
   - сохраняет входящее сообщение;
   - запрашивает `IntentManager.route`.
4. `IntentManager` отправляет сообщение и минимальный контекст в OpenAI API.
5. Если LLM возвращает reminder-intent, `AssistantService` передает выполнение в `ReminderService`.
6. Для `intent="reminder_create"` и заполненного `due_at` `ReminderService.create` сохраняет запись в `reminders` со статусом `pending`.
7. Пользователь получает подтверждение с человекочитаемым временем.

Формат подтверждения:

- сегодня: `Готово. Напомню "сводить ребенка в поликлинику" в 16:26`;
- завтра: `Готово. Напомню "..." завтра в 16:26`;
- послезавтра: `Готово. Напомню "..." послезавтра в 16:26`;
- через 3-7 дней: `Готово. Напомню "..." во вторник в 16:26`;
- дальше 7 дней: `Готово. Напомню "..." 26.06 в 16:26`.

## Запрос к LLM

Модель берется из `OPENAI_MODEL`. Сейчас в `.env.example` указано:

```env
OPENAI_MODEL=gpt-4.1-mini
```

`IntentManager` использует OpenAI Responses API:

```python
response = await client.responses.create(
    model=settings.openai_model,
    input=[
        {"role": "system", "content": INTENT_MANAGER_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ],
)
```

System prompt требует вернуть только валидный JSON. Строгий список intent:

```text
unknown, reminder_create, reminder_need_info, reminder_list, reminder_history, reminder_delete
```

Подробный контракт описан в [INTENT_MANAGER.md](INTENT_MANAGER.md).

Для относительных дат backend передает в LLM текущие дату/время и таймзону пользователя:

```json
{
  "now": "2026-06-09T16:25:00+03:00",
  "timezone": "Europe/Moscow",
  "message": "Хочу сводить ребенка в поликлинику, напомни через минуту",
  "recent_context": [
    {"role": "user", "content": "Хочу сводить ребенка в поликлинику, напомни через минуту"}
  ]
}
```

## Ожидаемый ответ LLM

Для полноценного напоминания ожидается JSON примерно такого вида:

```json
{
  "intent": "reminder_create",
  "confidence": 0.95,
  "reply": null,
  "topic_key": "general",
  "task_text": "сводить ребенка в поликлинику",
  "reminder_text": "сводить ребенка в поликлинику",
  "due_at": "2026-06-09T16:26:00+03:00",
  "event_title": null,
  "event_start": null,
  "event_end": null,
  "attendees": [],
  "needs_clarification": false,
  "clarification_question": null,
  "extracted_context": {}
}
```

Если времени недостаточно, LLM должен вернуть `intent="reminder_need_info"`, например:

```json
{
  "intent": "reminder_need_info",
  "confidence": 0.8,
  "reply": null,
  "topic_key": "general",
  "task_text": "сводить ребенка в поликлинику",
  "reminder_text": "сводить ребенка в поликлинику",
  "due_at": null,
  "event_title": null,
  "event_start": null,
  "event_end": null,
  "attendees": [],
  "needs_clarification": true,
  "clarification_question": "На какое время поставить напоминание?",
  "extracted_context": {}
}
```

Текст `clarification_question` генерирует LLM естественным языком. Если не
хватает только времени, предпочтительный формат - короткий вопрос вроде
`Во сколько?`.

При сохранении уточняющего ответа backend кладет исходный запрос пользователя в
payload поля `pending_user_text`. Это нужно, чтобы следующий ответ пользователя
объединялся с исходным запросом даже если сообщения в БД имеют одинаковый
`created_at`.

Backend нормализует пустые строки в `due_at`, `event_start`, `event_end` в `null`,
а отсутствующие `attendees` и `extracted_context` заменяет на пустые структуры.

## Правила интерпретации времени

Текущие правила задаются system prompt:

- относительные даты интерпретируются относительно `now` и `timezone`;
- "в обед" означает 13:00 локального времени пользователя;
- если точного времени недостаточно, нужно задать уточняющий вопрос.

Форматирование текста подтверждения выполняется в Python, а не через LLM. Причина: LLM отвечает за извлечение `due_at`, а выбор фразы "завтра", "во вторник" или "26.06" должен быть детерминированным.

## Хранение в БД

Напоминания хранятся в таблице `reminders`.

Основные поля:

- `user_id` - владелец напоминания;
- `text` - текст напоминания;
- `due_at` - время с timezone;
- `status` - `pending`, `sent` или `cancelled`;
- `source_message_id` - ссылка на исходное напоминание для переноса.

Созданное напоминание получает статус `pending`.

## Отправка напоминаний

`ReminderLoop` запускается при старте FastAPI-приложения.

Каждые 20 секунд он:

1. выбирает до 50 записей `reminders`, где:
   - `status = "pending"`;
   - `due_at <= now()`;
2. присоединяет пользователя;
3. отправляет сообщение в Telegram:

```text
Вы просили напомнить: включить чайник
```

4. добавляет inline-кнопки:
   - `ОК`;
   - `Перенести на 5 минут`;
5. переводит reminder в `sent`;
6. коммитит транзакцию.

Каждый пользователь получает только свои напоминания: отправка идет на `User.telegram_user_id`, найденный через `Reminder.user_id`.

## Кнопка ОК

Telegram присылает `callback_query` с `callback_data`:

```text
reminder:ok:<reminder_id>
```

Backend:

1. отвечает на callback через `answerCallbackQuery`;
2. вызывает `editMessageReplyMarkup`, чтобы убрать inline-кнопки;
3. не меняет запись reminder в БД, потому что она уже имеет статус `sent`.

Если Telegram API не смог убрать кнопки, ошибка логируется, но webhook все равно не должен падать в `500`.

## Кнопка "Перенести на 5 минут"

Telegram присылает `callback_query` с `callback_data`:

```text
reminder:snooze5:<reminder_id>
```

Backend:

1. проверяет, что reminder принадлежит пользователю, который нажал кнопку;
2. ищет уже существующий pending-перенос с `source_message_id=<reminder_id>`;
3. если такого переноса нет, создает новое напоминание:
   - `user_id` как у исходного;
   - `text` как у исходного;
   - `due_at = now UTC + 5 минут`;
   - `source_message_id = <reminder_id>`;
4. отвечает на callback текстом `Перенесено на 5 минут`;
5. убирает inline-кнопки с исходного Telegram-сообщения.

Проверка существующего pending-переноса нужна для идемпотентности: Telegram может повторить callback, если раньше webhook вернул ошибку.

## Просмотр и удаление будущих напоминаний

Если пользователь просит показать свои напоминания, intent-manager должен вернуть
`intent="reminder_list"`. `AssistantService` строит страницу будущих `pending`
reminders.

Если пользователь просит удалить или отменить напоминание свободным текстом,
intent-manager должен вернуть `intent="reminder_delete"`. Backend не удаляет
напоминание по текстовому описанию, а показывает тот же список будущих
напоминаний с кнопками удаления.

Список включает только напоминания текущего пользователя:

- `status = "pending"`;
- `due_at > now`;
- сортировка от ближайших к более поздним.

Размер страницы сейчас 5 напоминаний.

Пример ответа:

```text
Будущие напоминания, страница 1/2:
1. "поесть" в 18:32
2. "17 июня у нас театр" во вторник в 09:00
```

К каждой строке добавляется inline-кнопка удаления:

```text
X 1
X 2
```

Callback удаления:

```text
reminder:delete:<reminder_id>:<page>
```

Backend проверяет, что reminder принадлежит пользователю, который нажал кнопку, что reminder все еще `pending` и что `due_at` в будущем. После удаления статус меняется на `cancelled`, а текущее Telegram-сообщение редактируется и показывает обновленную страницу.

Навигация по страницам идет через inline-кнопки `Назад` и `Вперед`.

Callback навигации:

```text
reminder:list:<page>
```

История напоминаний также поддерживает навигацию:

```text
reminder:history:<page>
```

## Текущие ограничения

- Нет Alembic-миграций, таблицы создаются через `metadata.create_all`.
- Нет отдельного retry/backoff для ошибок Telegram при отправке напоминания.
- Нет тестов на форматирование времени и callback-перенос.
- Голосовые сообщения пока не транскрибируются.
