from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.intent_manager import IntentManager
from app.core.settings import settings
from app.db.models import ReminderStatus
from app.services.reminders import ReminderService
from app.services.schemas import AssistantAction, AssistantResponse, IncomingTelegramMessage
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
        self.intent_manager = IntentManager()

    async def handle_telegram_message(self, payload: IncomingTelegramMessage) -> AssistantResponse:
        text = payload.text or ""
        timezone = payload.timezone or settings.app_timezone
        user = await self.state.get_or_create_user(
            payload.telegram_user_id, payload.display_name, timezone
        )
        thread = await self.state.get_active_thread(user)
        previous_context = await self.state.recent_context_with_payload(thread, limit=4)
        context = build_intent_context(previous_context, text)
        await self.state.add_message(thread, "user", text, payload.raw)

        intent = await self.intent_manager.route(text, user.timezone, context)

        if intent.intent == "reminder_need_info":
            reply = intent.clarification_question or "Уточните детали, пожалуйста."
            intent_payload = intent.model_dump(mode="json")
            intent_payload["pending_user_text"] = text
            await self.state.add_message(
                thread,
                "assistant",
                reply,
                intent_payload,
            )
            await self.session.commit()
            return AssistantResponse(text=reply)

        if intent.intent in {"reminder_list", "reminder_delete"}:
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

        reply = intent.reply or "Я не смог разобрать запрос. Попробуйте сформулировать иначе."
        await self.state.add_message(thread, "assistant", reply, intent.model_dump(mode="json"))
        await self.session.commit()
        return AssistantResponse(text=reply)


def build_intent_context(
    previous_context: list[dict[str, Any]],
    current_text: str,
) -> list[dict[str, str]]:
    for index in range(len(previous_context) - 1, -1, -1):
        previous_assistant = previous_context[index]
        previous_payload = previous_assistant.get("payload") or {}
        if (
            previous_assistant["role"] != "assistant"
            or previous_payload.get("intent") != "reminder_need_info"
        ):
            continue

        pending_user_text = previous_payload.get("pending_user_text")
        if not isinstance(pending_user_text, str) or not pending_user_text.strip():
            pending_user_text = find_previous_user_text(previous_context, index)
        if not pending_user_text:
            break

        return [
            {"role": "user", "content": pending_user_text},
            {
                "role": previous_assistant["role"],
                "content": previous_assistant["content"],
            },
            {"role": "user", "content": current_text},
        ]
    return [{"role": "user", "content": current_text}]


def find_previous_user_text(
    previous_context: list[dict[str, Any]], before_index: int
) -> str | None:
    for item in reversed(previous_context[:before_index]):
        if item["role"] == "user" and item["content"].strip():
            return item["content"]
    return None


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
