# Web Search

Этот документ фиксирует текущее поведение поручений с интернет-поиском.

## Назначение

Web-search используется для поручений вида "найди", "сравни", "подбери" и "проверь".
Backend создает `DelegatedTask`, запускает поиск через OpenAI Responses API и хранит
результат в `delegated_tasks.result`.

## Пользовательская настройка

- По умолчанию город поиска для пользователя - `Москва`.
- Команда `/location Город` сохраняет `users.location`.
- Если пользователь явно указал город в самом запросе, он имеет приоритет над
  сохраненным городом.

## Текущий поток

1. `IntentManager` выбирает `web_search` или `web_search_update`.
2. `AssistantService` сохраняет задачу в `DelegatedTask`.
3. `WebSearchRunner` вызывает `web_search` tool через Responses API.
4. В prompt передаются цель задачи, город пользователя и структурированный контекст.
5. Результат сохраняется в `DelegatedTask.result`.
6. Если потом пользователь просит напомнить о выбранном варианте, backend передает
   ограниченный фрагмент результата в reference-resolver.

## Prompt-правила

- По умолчанию искать розничные варианты и малые партии, если пользователь не просит опт.
- Для товаров сначала проверять маркетплейсы, розничные магазины и строительные сети.
- Оптовые варианты показывать как запасной путь, если они не запрошены явно.
- Не выдумывать цены, наличие, доставку и ссылки.

## Контекст

- В context задачи сохраняются структурированные уточнения пользователя.
- В result сохраняется текстовый ответ поиска.
- В контекст для напоминаний попадает ограниченный excerpt результата, чтобы можно
  было сохранить конкретный выбранный вариант, а не только общий предмет поиска.

## Связанные файлы

- [services/assistant/app/services/web_search.py](../services/assistant/app/services/web_search.py)
- [services/assistant/app/services/conversation_context.py](../services/assistant/app/services/conversation_context.py)
- [services/assistant/app/services/reference_resolver.py](../services/assistant/app/services/reference_resolver.py)
- [services/assistant/app/api/telegram.py](../services/assistant/app/api/telegram.py)
