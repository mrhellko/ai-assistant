import json
from typing import Any

from openai import AsyncOpenAI

from app.core.settings import settings
from app.db.models import DelegatedTask

TASK_RESULT_TEXT_LIMIT = 2000


REFERENCE_RESOLVER_SYSTEM_PROMPT = """
You resolve short references in Russian reminder text for a personal assistant.
Return only valid JSON. Do not add markdown or explanatory text.

Task:
- You receive the user's current message, the extracted reminder_text, and one active task.
- If the current message or reminder_text explicitly refers to the active task, rewrite
  reminder_text so it contains the concrete object from the active task.
- The active task can include result_text with search results. If the user refers to
  a specific chosen/favorite option, include the option name, seller/store, price,
  delivery, and link when those details are present in result_text.
- If there is no explicit reference to the active task, return reminder_text unchanged.
- Do not add facts that are not present in the active task objective/context/result_text.
- Keep the result short and natural in Russian.

Return this JSON object:
{
  "resolved_reminder_text": "string"
}
""".strip()


class TaskReferenceResolver:
    def __init__(self, client: AsyncOpenAI | None, model: str) -> None:
        self.client = client
        self.model = model

    @classmethod
    def from_settings(cls) -> "TaskReferenceResolver":
        client = AsyncOpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None
        return cls(client=client, model=settings.openai_model)

    async def resolve(
        self,
        *,
        current_text: str,
        reminder_text: str,
        active_task: DelegatedTask | None,
    ) -> str:
        if not self.client or not active_task:
            return reminder_text

        user_content = json.dumps(
            {
                "current_message": current_text,
                "reminder_text": reminder_text,
                "active_task": task_payload(active_task),
            },
            ensure_ascii=False,
        )
        try:
            response = await self.client.responses.create(
                model=self.model,
                input=[
                    {"role": "system", "content": REFERENCE_RESOLVER_SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
            )
            data = json.loads(json_only(response.output_text))
        except Exception:
            return reminder_text
        resolved = data.get("resolved_reminder_text")
        if isinstance(resolved, str) and resolved.strip():
            return resolved.strip()
        return reminder_text


def task_payload(task: DelegatedTask) -> dict[str, Any]:
    payload = {
        "objective": task.objective,
        "context": task.context or {},
    }
    result_text = task_result_text(task)
    if result_text:
        payload["result_text"] = result_text
    return payload


def task_result_text(task: DelegatedTask) -> str | None:
    result = task.result or {}
    if not isinstance(result, dict):
        return None
    text = result.get("text")
    if not isinstance(text, str) or not text.strip():
        return None
    text = text.strip()
    if len(text) <= TASK_RESULT_TEXT_LIMIT:
        return text
    return f"{text[:TASK_RESULT_TEXT_LIMIT].rstrip()}..."


def json_only(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    return text.strip()
