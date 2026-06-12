from typing import Any

from openai import AsyncOpenAI

from app.core.settings import settings
from app.db.models import DelegatedTask


WEB_SEARCH_SYSTEM_PROMPT = """
Ты выполняешь интернет-поиск для личного Telegram-ассистента.
Отвечай по-русски, кратко и практически.

Правила:
- Используй web search для актуальных данных.
- Если пользователь не просит опт, B2B или поставку партиями, считай, что нужен
  розничный вариант или малая партия для частной покупки.
- Для товаров сначала ищи розничные площадки, маркетплейсы и строительные магазины,
  где можно купить 1 штуку или небольшой отрез/объем. Оптовые поставщики допустимы
  только как запасной вариант или если пользователь явно просит опт.
- Если по обычному поиску лучше находятся конкретные магазины вроде маркетплейсов
  или строительных сетей, проверь такие источники отдельно.
- Если пользователь ищет товар или поставщика, дай 3-5 вариантов, если они есть.
- Для каждого варианта укажи название, цену/наличие/доставку, если удалось найти,
  и ссылку.
- Отделяй розничные варианты от оптовых, если в выдаче есть оба типа.
- Если данных мало или они ненадежны, явно скажи, что нужно уточнить.
- Не выдумывай цены, наличие и ссылки.
- В конце дай короткую рекомендацию или следующий шаг.
""".strip()


class WebSearchRunner:
    def __init__(self, client: AsyncOpenAI | None = None, model: str | None = None) -> None:
        self.client = client or (
            AsyncOpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None
        )
        self.model = model or settings.openai_model

    async def run(self, task: DelegatedTask, user_location: str = "Москва") -> dict[str, Any]:
        if not self.client:
            return {
                "status": "unavailable",
                "text": "Интернет-поиск сейчас недоступен: не задан OPENAI_API_KEY.",
            }

        response = await self.client.responses.create(
            model=self.model,
            tools=[{"type": "web_search", "search_context_size": "low"}],
            tool_choice="required",
            input=[
                {"role": "system", "content": WEB_SEARCH_SYSTEM_PROMPT},
                {"role": "user", "content": search_prompt(task, user_location)},
            ],
        )
        return {
            "status": "completed",
            "text": response.output_text.strip(),
        }


def search_prompt(task: DelegatedTask, user_location: str = "Москва") -> str:
    return "\n".join(
        [
            f"Задача: {task.objective}",
            f"Город пользователя: {user_location or 'Москва'}",
            (
                "Если пользователь не указал другой город или регион в задаче, "
                "ищи варианты для города пользователя."
            ),
            f"Контекст и ограничения: {task.context or {}}",
        ]
    )
