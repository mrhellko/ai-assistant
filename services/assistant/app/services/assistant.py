from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.intent_router import IntentRouter
from app.core.settings import settings
from app.integrations.google_calendar import GoogleCalendar
from app.services.reminders import ReminderService
from app.services.schemas import AssistantAction, AssistantResponse, IncomingTelegramMessage
from app.services.user_state import UserState
from app.services.web_tasks import WebTaskService


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
            reply = f"Готово. Напомню: {reminder.text}"
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
                    actions=[AssistantAction(type="request_google_auth", payload={"url": auth_url})],
                )
            result = await calendar.create_event(user.id, intent)
            reply = f"Встреча создана: {result.get('htmlLink', intent.event_title or 'событие')}"
            await self.state.add_message(thread, "assistant", reply, result)
            await self.session.commit()
            return AssistantResponse(text=reply)

        if intent.intent == "web_task":
            result = await WebTaskService(self.session).create_or_update(user.id, thread.id, intent, text)
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

