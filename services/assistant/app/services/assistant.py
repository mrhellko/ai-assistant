from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.intent_router import IntentRouter
from app.core.settings import settings
from app.integrations.google_calendar import GoogleCalendar
from app.services.reminders import ReminderService
from app.services.schemas import AssistantAction, AssistantResponse, IncomingTelegramMessage
from app.services.user_state import UserState
from app.services.web_tasks import WebTaskService


REMINDER_LIST_PAGE_SIZE = 5
REMINDER_LIST_REQUEST_PATTERNS = (
    "мои напомин",
    "мои уведом",
    "список напомин",
    "список уведом",
    "покажи напомин",
    "покажи уведом",
    "какие напомин",
    "какие уведом",
    "будущие напомин",
    "будущие уведом",
    "все напомин",
    "все уведом",
)

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
        self.intent_router = IntentRouter()

    async def handle_telegram_message(self, payload: IncomingTelegramMessage) -> AssistantResponse:
        text = payload.text or ""
        timezone = payload.timezone or settings.app_timezone
        user = await self.state.get_or_create_user(
            payload.telegram_user_id, payload.display_name, timezone
        )
        thread = await self.state.get_active_thread(user)
        await self.state.add_message(thread, "user", text, payload.raw)
        context = await self.state.recent_context(thread)

        if is_reminder_list_request(text):
            response = await build_future_reminders_response(
                ReminderService(self.session),
                user.id,
                user.timezone,
                page=0,
            )
            await self.state.add_message(
                thread,
                "assistant",
                response.text,
                {"type": "list_reminders"},
            )
            await self.session.commit()
            return response

        intent = await self.intent_router.route(text, user.timezone, context)
        if intent.intent == "new_dialog":
            thread = await self.state.start_new_thread(user, intent.topic_key)
            await self.state.add_message(thread, "user", text, payload.raw)

        if intent.needs_clarification:
            reply = intent.clarification_question or "Уточните детали, пожалуйста."
            await self.state.add_message(thread, "assistant", reply, intent.model_dump(mode="json"))
            await self.session.commit()
            return AssistantResponse(text=reply)

        if intent.intent == "reminder":
            if not intent.due_at:
                reply = "На какое время поставить напоминание?"
                await self.state.add_message(thread, "assistant", reply)
                await self.session.commit()
                return AssistantResponse(text=reply)

            reminder = await ReminderService(self.session).create(
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
                        payload={"reminder_id": reminder.id, "due_at": reminder.due_at.isoformat()},
                    )
                ],
            )

        if intent.intent == "calendar_event":
            calendar = GoogleCalendar(self.session)
            if not await calendar.has_credentials(user.id):
                auth_url = calendar.authorization_url(user.id)
                reply = "Чтобы создавать встречи, подключите Google Calendar."
                await self.state.add_message(thread, "assistant", reply, {"auth_url": auth_url})
                await self.session.commit()
                return AssistantResponse(
                    text=reply,
                    actions=[
                        AssistantAction(type="request_google_auth", payload={"url": auth_url})
                    ],
                )
            result = await calendar.create_event(user.id, intent)
            reply = f"Встреча создана: {result.get('htmlLink', intent.event_title or 'событие')}"
            await self.state.add_message(thread, "assistant", reply, result)
            await self.session.commit()
            return AssistantResponse(text=reply)

        if intent.intent == "web_task":
            result = await WebTaskService(self.session).create_or_update(
                user.id, thread.id, intent, text
            )
            reply = result["message"]
            await self.state.add_message(thread, "assistant", reply, result)
            await self.session.commit()
            return AssistantResponse(
                text=reply,
                actions=[AssistantAction(type="run_web_search", payload=result)],
            )

        reply = intent.reply or "Я понял. Продолжайте."
        await self.state.add_message(thread, "assistant", reply, intent.model_dump(mode="json"))
        await self.session.commit()
        return AssistantResponse(text=reply)


def is_reminder_list_request(text: str) -> bool:
    lower = text.strip().lower()
    if "напомни" in lower:
        return False
    return any(pattern in lower for pattern in REMINDER_LIST_REQUEST_PATTERNS)


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


def quote_reminder_text(text: str) -> str:
    return f'"{text}"'


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
