from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.intent_manager import IntentManager
from app.core.settings import settings
from app.db.models import ReminderStatus, UserIntentState
from app.services.intent_state import IntentStateService
from app.services.reminders import ReminderService
from app.services.schemas import (
    AssistantAction,
    AssistantResponse,
    IncomingTelegramMessage,
    IntentResult,
)
from app.services.user_state import UserState


REMINDER_LIST_PAGE_SIZE = 5

WEEKDAY_REMINDER_LABELS = {
    0: "в понедельник",
    1: "во вторник",
    2: "в среду",
    3: "в четверг",
    4: "в пятницу",
    5: "в субботу",
    6: "в воскресенье",
}


class AssistantService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.state = UserState(session)
        self.intent_state = IntentStateService(session)
        self.intent_manager = IntentManager()

    async def handle_telegram_message(self, payload: IncomingTelegramMessage) -> AssistantResponse:
        text = payload.text or ""
        timezone = payload.timezone or settings.app_timezone
        user = await self.state.get_or_create_user(
            payload.telegram_user_id, payload.display_name, timezone
        )
        thread = await self.state.get_active_thread(user)
        active_intent_state = await self.intent_state.get_active(user.id)
        context = build_intent_context(active_intent_state, text)
        await self.state.add_message(thread, "user", text, payload.raw)

        intent = await self.intent_manager.route(self.session, text, user.timezone, context)

        if intent.intent == "reminder_need_info":
            reply = intent.clarification_question or "Уточните детали, пожалуйста."
            intent_payload = intent.model_dump(mode="json")
            intent_payload["pending_user_text"] = build_pending_user_text(
                active_intent_state,
                text,
                intent,
            )
            intent_payload["context_messages"] = build_pending_context_messages(
                active_intent_state,
                text,
                reply,
            )
            await self.intent_state.set_active(
                user.id,
                thread.id,
                intent.intent,
                intent_payload,
            )
            await self.state.add_message(
                thread,
                "assistant",
                reply,
                intent_payload,
            )
            await self.session.commit()
            return AssistantResponse(text=reply)

        if intent.intent in {"reminder_list", "reminder_delete"}:
            await self.intent_state.clear_active(user.id)
            reminder_service = ReminderService(self.session)
            response = await build_future_reminders_response(
                reminder_service,
                user.id,
                user.timezone,
                page=0,
            )
            await self.state.add_message(
                thread,
                "assistant",
                response.text,
                intent.model_dump(mode="json"),
            )
            await self.session.commit()
            return response

        if intent.intent == "reminder_history":
            await self.intent_state.clear_active(user.id)
            reminder_service = ReminderService(self.session)
            response = await build_reminder_history_response(
                reminder_service,
                user.id,
                user.timezone,
                page=0,
            )
            await self.state.add_message(
                thread,
                "assistant",
                response.text,
                intent.model_dump(mode="json"),
            )
            await self.session.commit()
            return response

        if intent.intent == "reminder_create":
            reminder_service = ReminderService(self.session)
            if not intent.due_at:
                reply = (
                    intent.clarification_question
                    or "Не хватает данных для напоминания. Укажите, что и когда напомнить."
                )
                intent_payload = intent.model_dump(mode="json")
                intent_payload["pending_user_text"] = (
                    build_pending_user_text(active_intent_state, text, intent)
                )
                intent_payload["context_messages"] = build_pending_context_messages(
                    active_intent_state,
                    text,
                    reply,
                )
                await self.intent_state.set_active(
                    user.id,
                    thread.id,
                    "reminder_need_info",
                    intent_payload,
                )
                await self.state.add_message(
                    thread,
                    "assistant",
                    reply,
                    intent.model_dump(mode="json"),
                )
                await self.session.commit()
                return AssistantResponse(text=reply)

            reminder = await reminder_service.create(
                user.id,
                intent.reminder_text or intent.task_text or text,
                intent.due_at,
            )
            await self.intent_state.clear_active(user.id)
            due_text = format_reminder_due_text(reminder.due_at, user.timezone)
            reply = f"Готово. Напомню {quote_reminder_text(reminder.text)} {due_text}"
            await self.state.add_message(thread, "assistant", reply, {"reminder_id": reminder.id})
            await self.session.commit()
            return AssistantResponse(
                text=reply,
                actions=[
                    AssistantAction(
                        type="create_reminder",
                        payload={
                            "reminder_id": reminder.id,
                            "due_at": reminder.due_at.isoformat(),
                        },
                    )
                ],
            )

        await self.intent_state.clear_active(user.id)
        reply = intent.reply or "Я не смог разобрать запрос. Попробуйте сформулировать иначе."
        await self.state.add_message(thread, "assistant", reply, intent.model_dump(mode="json"))
        await self.session.commit()
        return AssistantResponse(text=reply)


def build_intent_context(
    active_intent_state: UserIntentState | None,
    current_text: str,
) -> list[dict[str, str]]:
    if active_intent_state and active_intent_state.intent == "reminder_need_info":
        payload = active_intent_state.payload or {}
        context_messages = normalized_context_messages(payload)
        if context_messages:
            return [*context_messages, {"role": "user", "content": current_text}]

        pending_user_text = payload.get("pending_user_text")
        clarification_question = payload.get("clarification_question")
        if (
            isinstance(pending_user_text, str)
            and pending_user_text.strip()
            and isinstance(clarification_question, str)
            and clarification_question.strip()
        ):
            return [
                {"role": "user", "content": pending_user_text},
                {"role": "assistant", "content": clarification_question},
                {"role": "user", "content": current_text},
            ]
    return [{"role": "user", "content": current_text}]


def normalized_context_messages(payload: dict) -> list[dict[str, str]]:
    raw_messages = payload.get("context_messages")
    if not isinstance(raw_messages, list):
        return []

    messages: list[dict[str, str]] = []
    for item in raw_messages:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = item.get("content")
        if role in {"user", "assistant"} and isinstance(content, str) and content.strip():
            messages.append({"role": role, "content": content})
    return messages


def pending_user_text(active_intent_state: UserIntentState | None) -> str | None:
    if not active_intent_state:
        return None
    payload = active_intent_state.payload or {}
    value = payload.get("pending_user_text")
    if isinstance(value, str) and value.strip():
        return value
    return None


def pending_clarification_question(active_intent_state: UserIntentState | None) -> str | None:
    if not active_intent_state:
        return None
    payload = active_intent_state.payload or {}
    value = payload.get("clarification_question")
    if isinstance(value, str) and value.strip():
        return value
    return None


def build_pending_user_text(
    active_intent_state: UserIntentState | None,
    current_text: str,
    intent: IntentResult,
) -> str:
    existing_text = pending_user_text(active_intent_state)
    extracted_text = extracted_reminder_text(intent)

    if not existing_text:
        return current_text
    if not extracted_text:
        return existing_text
    if is_generic_reminder_request(existing_text):
        return f"напомни {extracted_text}"
    if extracted_text.lower() in existing_text.lower():
        return existing_text
    return f"{existing_text} {extracted_text}"


def build_pending_context_messages(
    active_intent_state: UserIntentState | None,
    current_text: str,
    clarification_question: str,
) -> list[dict[str, str]]:
    previous_messages = []
    if active_intent_state:
        previous_messages = normalized_context_messages(active_intent_state.payload or {})

    if previous_messages:
        messages = previous_messages
    else:
        previous_text = pending_user_text(active_intent_state)
        previous_question = pending_clarification_question(active_intent_state)
        messages = [{"role": "user", "content": previous_text}] if previous_text else []
        if previous_question:
            messages.append({"role": "assistant", "content": previous_question})

    messages = [
        *messages,
        {"role": "user", "content": current_text},
        {"role": "assistant", "content": clarification_question},
    ]
    return compact_adjacent_user_messages(messages)


def compact_adjacent_user_messages(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    compacted: list[dict[str, str]] = []
    for message in messages:
        if (
            compacted
            and compacted[-1]["role"] == "user"
            and message["role"] == "user"
        ):
            compacted[-1]["content"] = f"{compacted[-1]['content']} {message['content']}"
            continue
        compacted.append(message)
    return compacted


def extracted_reminder_text(intent: IntentResult) -> str | None:
    for value in (
        intent.reminder_text,
        intent.task_text,
        intent.extracted_context.get("reminder_text"),
    ):
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def is_generic_reminder_request(text: str) -> bool:
    normalized = text.strip().lower()
    return normalized in {
        "напомни",
        "напомнить",
        "поставь напоминание",
        "создай напоминание",
    }


async def build_future_reminders_response(
    reminder_service: ReminderService,
    user_id: str,
    timezone: str,
    page: int,
) -> AssistantResponse:
    page = max(page, 0)
    reminders, total = await reminder_service.list_future(
        user_id,
        page,
        REMINDER_LIST_PAGE_SIZE,
    )
    if total == 0:
        return AssistantResponse(text="Будущих напоминаний нет.")

    last_page = max((total - 1) // REMINDER_LIST_PAGE_SIZE, 0)
    page = min(page, last_page)
    if not reminders and page <= last_page:
        reminders, total = await reminder_service.list_future(
            user_id,
            page,
            REMINDER_LIST_PAGE_SIZE,
        )

    lines = [f"Будущие напоминания, страница {page + 1}/{last_page + 1}:"]
    keyboard: list[list[dict[str, str]]] = []
    for index, reminder in enumerate(reminders, start=1):
        number = page * REMINDER_LIST_PAGE_SIZE + index
        due_text = format_reminder_due_text(reminder.due_at, timezone)
        lines.append(f"{number}. {quote_reminder_text(reminder.text)} {due_text}")
        keyboard.append(
            [
                {
                    "text": f"X {number}",
                    "callback_data": f"reminder:delete:{reminder.id}:{page}",
                }
            ]
        )

    navigation: list[dict[str, str]] = []
    if page > 0:
        navigation.append({"text": "Назад", "callback_data": f"reminder:list:{page - 1}"})
    if page < last_page:
        navigation.append({"text": "Вперед", "callback_data": f"reminder:list:{page + 1}"})
    if navigation:
        keyboard.append(navigation)
    keyboard.append([{"text": "Закрыть", "callback_data": "reminder:ok:list"}])

    return AssistantResponse(
        text="\n".join(lines),
        reply_markup={"inline_keyboard": keyboard},
    )


async def build_reminder_history_response(
    reminder_service: ReminderService,
    user_id: str,
    timezone: str,
    page: int,
) -> AssistantResponse:
    page = max(page, 0)
    reminders, total = await reminder_service.list_history(
        user_id,
        page,
        REMINDER_LIST_PAGE_SIZE,
    )
    if total == 0:
        return AssistantResponse(text="История напоминаний пуста.")

    last_page = max((total - 1) // REMINDER_LIST_PAGE_SIZE, 0)
    page = min(page, last_page)
    if not reminders and page <= last_page:
        reminders, total = await reminder_service.list_history(
            user_id,
            page,
            REMINDER_LIST_PAGE_SIZE,
        )

    lines = [f"История напоминаний, страница {page + 1}/{last_page + 1}:"]
    keyboard: list[list[dict[str, str]]] = []
    for index, reminder in enumerate(reminders, start=1):
        number = page * REMINDER_LIST_PAGE_SIZE + index
        due_text = format_reminder_due_text(reminder.due_at, timezone)
        status_text = format_reminder_status(reminder.status)
        lines.append(f"{number}. {quote_reminder_text(reminder.text)} {due_text} - {status_text}")

    navigation: list[dict[str, str]] = []
    if page > 0:
        navigation.append({"text": "Назад", "callback_data": f"reminder:history:{page - 1}"})
    if page < last_page:
        navigation.append({"text": "Вперед", "callback_data": f"reminder:history:{page + 1}"})
    if navigation:
        keyboard.append(navigation)
    keyboard.append([{"text": "Закрыть", "callback_data": "reminder:ok:history"}])

    return AssistantResponse(
        text="\n".join(lines),
        reply_markup={"inline_keyboard": keyboard},
    )


def quote_reminder_text(text: str) -> str:
    return f'"{text}"'


def format_reminder_status(status: str) -> str:
    labels = {
        ReminderStatus.pending.value: "ожидает",
        ReminderStatus.sent.value: "отправлено",
        ReminderStatus.cancelled.value: "отменено",
    }
    return labels.get(status, status)


def format_reminder_due_text(due_at: datetime, timezone: str) -> str:
    tz = ZoneInfo(timezone)
    local_due_at = due_at.astimezone(tz) if due_at.tzinfo else due_at.replace(tzinfo=tz)
    local_now = datetime.now(tz)
    day_delta = (local_due_at.date() - local_now.date()).days
    time_text = local_due_at.strftime("%H:%M")

    if day_delta == 0:
        return f"в {time_text}"
    if day_delta == 1:
        return f"завтра в {time_text}"
    if day_delta == 2:
        return f"послезавтра в {time_text}"
    if 3 <= day_delta <= 7:
        return f"{WEEKDAY_REMINDER_LABELS[local_due_at.weekday()]} в {time_text}"
    return f"{local_due_at:%d.%m} в {time_text}"
