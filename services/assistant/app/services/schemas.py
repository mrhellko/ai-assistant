from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class IncomingTelegramMessage(BaseModel):
    telegram_user_id: str
    text: str | None = None
    voice_file_id: str | None = None
    display_name: str | None = None
    timezone: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class AssistantAction(BaseModel):
    type: Literal[
        "send_message",
        "request_google_auth",
        "create_reminder",
        "create_calendar_event",
        "run_web_search",
    ]
    payload: dict[str, Any] = Field(default_factory=dict)


class AssistantResponse(BaseModel):
    text: str
    actions: list[AssistantAction] = Field(default_factory=list)
    reply_markup: dict[str, Any] | None = None


class IntentResult(BaseModel):
    intent: Literal[
        "unknown",
        "reminder_create",
        "reminder_need_info",
        "reminder_list",
        "reminder_history",
        "reminder_delete",
        "thread_new",
        "thread_forget",
        "web_search",
        "web_search_update",
    ]
    confidence: float = 0.0
    reply: str | None = None
    topic_key: str = "general"
    task_text: str | None = None
    reminder_text: str | None = None
    due_at: datetime | None = None
    event_title: str | None = None
    event_start: datetime | None = None
    event_end: datetime | None = None
    attendees: list[str] = Field(default_factory=list)
    needs_clarification: bool = False
    clarification_question: str | None = None
    extracted_context: dict[str, Any] = Field(default_factory=dict)
