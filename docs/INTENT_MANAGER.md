# Intent Manager

`IntentManager` - единственная точка классификации пользовательского текста перед
передачей запроса в доменные модули. Сейчас он живет в
`services/assistant/app/agents/intent_manager.py`.

## Задача

Модуль принимает текст пользователя, текущую дату/время, таймзону и минимальный
контекст, затем возвращает строго структурированный JSON. Backend не пытается
угадывать намерение локальными шаблонами фраз.

## Поддерживаемые intent

Список intent хранится в таблице `intent_definitions` и используется при сборке
system prompt. Пока в проекте нет Alembic, таблица наполняется deterministic
bootstrap-кодом при старте приложения. После ввода Alembic эти записи должны
переехать в миграцию/seed-миграцию, а не заполняться пользователем.

Текущий справочник:

- `unknown` - запрос не понят или пока не поддерживается.
- `reminder_create` - создать новое напоминание.
- `reminder_need_info` - запрос относится к напоминаниям, но не хватает данных.
- `reminder_list` - показать будущие активные напоминания.
- `reminder_history` - показать историю напоминаний.
- `reminder_delete` - удалить или отменить напоминание.

Для `reminder_delete` backend не удаляет запись по свободному тексту. Он
показывает будущие напоминания с кнопками удаления, чтобы пользователь явно
выбрал нужную запись.

## Контракт ответа

LLM должна вернуть только валидный JSON без Markdown:

```json
{
  "intent": "unknown",
  "confidence": 0.0,
  "reply": null,
  "topic_key": "general",
  "task_text": null,
  "reminder_text": null,
  "due_at": null,
  "event_title": null,
  "event_start": null,
  "event_end": null,
  "attendees": [],
  "needs_clarification": false,
  "clarification_question": null,
  "extracted_context": {}
}
```

Поля `event_*`, `attendees` и `extracted_context` оставлены в контракте, чтобы не
ломать общую схему `IntentResult`, но текущий intent-manager ими не управляет.

## Правила контекста

Контекст специально ограничен:

- обычный запрос: только текущее сообщение пользователя;
- ответ на уточнение: три сообщения - исходный запрос пользователя, уточняющий
  вопрос ассистента, новый ответ пользователя.

Расширенный контекст включается только если у пользователя есть активная запись
в `user_intent_states` с `intent="reminder_need_info"`. Исходный пользовательский
запрос хранится в `payload.pending_user_text`, уточняющий вопрос - в
`payload.clarification_question`.

Это снижает риск, что LLM начнет фантазировать историю напоминаний на основе
старого диалога. Историю и списки должен отдавать модуль напоминаний из БД.

## Состояние пользователя

Текущий pending intent хранится явно в таблице `user_intent_states`.

Основные поля:

- `user_id` - владелец состояния;
- `thread_id` - thread, в котором состояние создано;
- `intent` - pending intent, сейчас используется `reminder_need_info`;
- `status` - `active` или `closed`;
- `payload` - структурированные данные состояния.

Для `reminder_need_info` payload содержит:

```json
{
  "intent": "reminder_need_info",
  "clarification_question": "Во сколько?",
  "pending_user_text": "напомни поесть"
}
```

После успешного `reminder_create`, `reminder_list`, `reminder_history`,
`reminder_delete` или `unknown` активное состояние пользователя закрывается.

## Поток обработки

1. Telegram webhook передает текст в `AssistantService`.
2. `AssistantService` сохраняет сообщение пользователя.
3. `AssistantService` читает активное состояние пользователя из
   `user_intent_states`.
4. `IntentManager.route()` отправляет в OpenAI текущий запрос и минимальный
   контекст.
5. `AssistantService` исполняет результат:
   - `unknown` - возвращает `reply` или общий текст непонимания;
   - `reminder_need_info` - сохраняет активное состояние и возвращает
     `clarification_question`;
   - `reminder_create` - создает напоминание через `ReminderService`;
   - `reminder_list` - показывает будущие напоминания;
   - `reminder_history` - показывает историю напоминаний;
   - `reminder_delete` - показывает будущие напоминания с кнопками удаления.

## Уточнения

Текст уточняющего вопроса формирует LLM. Вопрос должен быть естественным и
спрашивать только недостающие сведения.

Пример:

```text
Пользователь: Напомни завтра сходить в больницу
Бот: Во сколько?
Пользователь: в 17:00
Бот: Готово. Напомню "сходить в больницу" завтра в 17:00
```

## Напоминания

Для `reminder_create` backend создает запись в `reminders` со статусом
`pending`.

Для `reminder_list` и `reminder_delete` backend выбирает только будущие активные
напоминания:

- `status = "pending"`;
- `due_at > now`;
- сортировка от ближайших к дальним.

Для `reminder_history` backend показывает последние напоминания
пользователя независимо от статуса.

## Fallback без OpenAI API

Если `OPENAI_API_KEY` не задан, `IntentManager` возвращает `unknown`. Локального
эвристического распознавания намерений больше нет.
