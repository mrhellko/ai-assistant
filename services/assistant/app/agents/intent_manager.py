import json
from datetime import datetime
from zoneinfo import ZoneInfo

from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import settings
from app.db.models import IntentDefinition
from app.services.intent_definitions import INTENT_DEFINITIONS, format_intent_definitions
from app.services.schemas import IntentResult


INTENT_MANAGER_SYSTEM_PROMPT_TEMPLATE = """
You are an intent manager for a Russian Telegram personal assistant.
Return only valid JSON. Do not add markdown or explanatory text.
Use recent_context only to understand the active topic, pending clarification,
and short references like "его", "этот вариант", or "ту встречу".
Do not answer reminder lists or reminder history from recent_context; those are
handled by backend database queries.

Allowed intent values are strictly:
{intent_definitions}

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

For intent=thread_new:
- use it only when the user explicitly asks to start a new dialog, new conversation,
  or clean topic.
- do not use it just because the user asks a new question; routing should switch
  actions automatically without requiring a new dialog command.

For intent=thread_forget:
- use it only when the user explicitly asks to forget, reset, or discard the current
  topic context.
- this means clearing active topic context, not deleting historical database records.

For intent=web_search:
- use it when the user asks to find, compare, research, select, or buy something using
  current internet information.
- set task_text to the full search objective.
- put structured constraints in extracted_context, for example object, material, size,
  length, budget, location, delivery, must_have, nice_to_have.
- do not use local assumptions; extract only what the user said.

For intent=web_search_update:
- use it when recent_context contains an active search task and the user refines it.
- set task_text to the full updated objective when possible, preserving relevant
  constraints from the active task.
- put changed or newly added constraints in extracted_context.
- if the user switches to another domain, such as reminders, use that domain intent
  instead of web_search_update.

For intent=unknown:
- set reply to a concise Russian message saying that the request is not understood.

Return this JSON object shape:
{{
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
  "extracted_context": {{}}
}}

Date rules:
- Interpret relative dates using now and timezone from the user payload.
- If the user says lunch without exact time, use 13:00 local time.
- If the user gives only a date without time, ask a clarification question.
- due_at must be ISO 8601 with timezone offset.

Examples:
- User: "Напомни завтра сходить в больницу"
  JSON: {{"intent":"reminder_need_info","clarification_question":"Во сколько?"}}
- Recent context:
  user: "Напомни завтра сходить в больницу"
  assistant: "Во сколько?"
  user: "в 17:00"
  JSON: {{
    "intent": "reminder_create",
    "reminder_text": "сходить в больницу",
    "due_at": "<tomorrow at 17:00 in timezone>"
  }}
""".strip()


class IntentManager:
    def __init__(self) -> None:
        self.client = (
            AsyncOpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None
        )

    async def route(
        self,
        session: AsyncSession,
        text: str,
        timezone: str,
        recent_context: list[dict[str, str]],
    ) -> IntentResult:
        if not self.client:
            return self._fallback()

        system_prompt = await self._system_prompt(session)
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
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
        )
        data = json.loads(self._json_only(response.output_text))
        return IntentResult.model_validate(self._normalize_result(data))

    async def _system_prompt(self, session: AsyncSession) -> str:
        definitions = await self._load_intent_definitions(session)
        return INTENT_MANAGER_SYSTEM_PROMPT_TEMPLATE.format(
            intent_definitions=format_intent_definitions(definitions)
        )

    async def _load_intent_definitions(self, session: AsyncSession) -> list[dict]:
        result = await session.execute(
            select(IntentDefinition)
            .where(IntentDefinition.is_active.is_(True))
            .order_by(IntentDefinition.sort_order.asc(), IntentDefinition.name.asc())
        )
        definitions = [
            {
                "name": item.name,
                "description": item.description,
                "details": item.details,
                "sort_order": item.sort_order,
            }
            for item in result.scalars().all()
        ]
        return definitions or INTENT_DEFINITIONS

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
