import json
from datetime import datetime
from zoneinfo import ZoneInfo

from openai import AsyncOpenAI

from app.core.settings import settings
from app.services.schemas import IntentResult


class IntentRouter:
    def __init__(self) -> None:
        self.client = AsyncOpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None

    async def route(
        self,
        text: str,
        timezone: str,
        recent_context: list[dict[str, str]],
    ) -> IntentResult:
        if not self.client:
            return self._fallback(text, timezone)

        now = datetime.now(ZoneInfo(timezone)).isoformat()
        prompt = {
            "role": "system",
            "content": (
                "You are an intent router for a Russian Telegram personal assistant. "
                "Return only valid JSON matching these fields: intent, confidence, reply, "
                "topic_key, task_text, reminder_text, due_at, event_title, event_start, "
                "event_end, attendees, needs_clarification, clarification_question, "
                "extracted_context. Supported intents: reminder, calendar_event, web_task, "
                "chat, new_dialog. Interpret relative dates using now and timezone. "
                "If user says lunch without exact time, use 13:00 local time. "
                "Keep topic_key stable for follow-ups, e.g. steel_bar_purchase."
            ),
        }
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
            input=[prompt, {"role": "user", "content": user_content}],
        )
        raw = response.output_text
        data = json.loads(self._json_only(raw))
        return IntentResult.model_validate(data)

    def _json_only(self, raw: str) -> str:
        text = raw.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:]
        return text.strip()

    def _fallback(self, text: str, timezone: str) -> IntentResult:
        lower = text.lower()
        if "напом" in lower:
            return IntentResult(
                intent="reminder",
                confidence=0.4,
                reminder_text=text,
                needs_clarification=True,
                clarification_question="На какое время поставить напоминание?",
            )
        if "встреч" in lower or "календар" in lower:
            return IntentResult(intent="calendar_event", confidence=0.35, task_text=text)
        if "найди" in lower or "где купить" in lower or "поиск" in lower:
            return IntentResult(intent="web_task", confidence=0.35, task_text=text)
        return IntentResult(intent="chat", confidence=0.2, reply=text)
