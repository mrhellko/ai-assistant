import json
from datetime import datetime
from zoneinfo import ZoneInfo

from openai import AsyncOpenAI

from app.core.settings import settings
from app.services.schemas import IntentResult


INTENT_MANAGER_SYSTEM_PROMPT = """
You are an intent manager for a Russian Telegram personal assistant.
Return only valid JSON. Do not add markdown or explanatory text.

Allowed intent values are strictly:
- unknown: the request is not understood or is outside currently supported reminder commands.
- reminder_create: create a new reminder. Requires reminder_text and due_at.
- reminder_need_info: the request is about reminders, but required information is missing.
- reminder_list: show future active reminders.
- reminder_history: show reminder history, including sent/cancelled/pending reminders.
- reminder_delete: the user wants to delete/cancel a reminder.

For intent=reminder_need_info:
- set clarification_question to a natural concise Russian question asking only
  for the missing information.
- use this when the user wants to create a reminder but text or time is missing.
- if only time is missing, ask only about time, e.g. "Во сколько?"
- if only reminder text is missing, ask only what to remind about.
- if recent_context contains your previous clarification and the current message completes it,
  return intent=reminder_create.

For intent=reminder_delete:
- use it when the user asks to remove, delete, cancel, or clear reminders.
- if the exact reminder is not safely identifiable, still return reminder_delete;
  the backend will show future reminders with delete buttons.

For intent=unknown:
- set reply to a concise Russian message saying that the request is not understood.

Return this JSON object shape:
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

Date rules:
- Interpret relative dates using now and timezone from the user payload.
- If the user says lunch without exact time, use 13:00 local time.
- If the user gives only a date without time, ask a clarification question.
- due_at must be ISO 8601 with timezone offset.

Examples:
- User: "Напомни завтра сходить в больницу"
  JSON: {"intent":"reminder_need_info","clarification_question":"Во сколько?"}
- Recent context:
  user: "Напомни завтра сходить в больницу"
  assistant: "Во сколько?"
  user: "в 17:00"
  JSON: {
    "intent": "reminder_create",
    "reminder_text": "сходить в больницу",
    "due_at": "<tomorrow at 17:00 in timezone>"
  }
""".strip()


class IntentManager:
    def __init__(self) -> None:
        self.client = (
            AsyncOpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None
        )

    async def route(
        self,
        text: str,
        timezone: str,
        recent_context: list[dict[str, str]],
    ) -> IntentResult:
        if not self.client:
            return self._fallback()

        now = datetime.now(ZoneInfo(timezone)).isoformat()
        user_content = json.dumps(
            {
                "now": now,
                "timezone": timezone,
                "message": text,
                "recent_context": recent_context,
            },
            ensure_ascii=False,
        )
        response = await self.client.responses.create(
            model=settings.openai_model,
            input=[
                {"role": "system", "content": INTENT_MANAGER_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
        )
        data = json.loads(self._json_only(response.output_text))
        return IntentResult.model_validate(self._normalize_result(data))

    def _json_only(self, raw: str) -> str:
        text = raw.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:]
        return text.strip()

    def _normalize_result(self, data: dict) -> dict:
        data["intent"] = data.get("intent") or "unknown"
        for key in ("due_at", "event_start", "event_end"):
            if data.get(key) == "":
                data[key] = None
        if data.get("attendees") is None:
            data["attendees"] = []
        if data.get("extracted_context") is None:
            data["extracted_context"] = {}
        if data["intent"] == "reminder_create" and data.get("due_at") is None:
            data["intent"] = "reminder_need_info"
        if data["intent"] == "reminder_need_info":
            data["needs_clarification"] = True
        return data

    def _fallback(self) -> IntentResult:
        return IntentResult(
            intent="unknown",
            confidence=0.0,
            reply="Я не смог разобрать запрос. Попробуйте сформулировать иначе.",
        )
