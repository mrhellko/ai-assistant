import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import settings
from app.db.models import Reminder, ReminderStatus, User
from app.db.session import get_session
from app.integrations.telegram import telegram_client
from app.services.assistant import AssistantService
from app.services.schemas import IncomingTelegramMessage

router = APIRouter()
logger = logging.getLogger(__name__)


def verify_telegram_secret(
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> None:
    if settings.telegram_webhook_secret and settings.telegram_webhook_secret != "change-me":
        if x_telegram_bot_api_secret_token != settings.telegram_webhook_secret:
            raise HTTPException(status_code=401, detail="invalid telegram webhook secret")


@router.post("/webhook")
async def telegram_webhook(
    update: dict[str, Any],
    _: None = Depends(verify_telegram_secret),
    session: AsyncSession = Depends(get_session),
) -> dict[str, bool]:
    callback_query = update.get("callback_query")
    if callback_query:
        await handle_callback_query(callback_query, session)
        return {"ok": True}

    message = update.get("message") or update.get("edited_message")
    if not message:
        return {"ok": True}

    chat = message.get("chat") or {}
    sender = message.get("from") or {}
    text = message.get("text")
    voice = message.get("voice") or {}
    chat_id = str(chat.get("id") or sender.get("id"))
    if not chat_id:
        return {"ok": True}
    if not text and voice:
        await telegram_client.send_message(
            chat_id,
            "Голосовые сообщения пока не подключены. Пришлите текстом, и я обработаю запрос.",
        )
        return {"ok": True}
    if not text:
        return {"ok": True}

    display_name = " ".join(
        part for part in [sender.get("first_name"), sender.get("last_name")] if part
    ) or sender.get("username")
    payload = IncomingTelegramMessage(
        telegram_user_id=str(sender.get("id") or chat_id),
        text=text,
        voice_file_id=voice.get("file_id"),
        display_name=display_name,
        raw=update,
    )
    response = await AssistantService(session).handle_telegram_message(payload)
    text_to_send = response.text
    for action in response.actions:
        if action.type == "request_google_auth" and action.payload.get("url"):
            text_to_send = f"{text_to_send}\n\n{action.payload['url']}"
    await telegram_client.send_message(chat_id, text_to_send)
    return {"ok": True}


async def handle_callback_query(
    callback_query: dict[str, Any],
    session: AsyncSession,
) -> None:
    callback_query_id = str(callback_query.get("id") or "")
    data = str(callback_query.get("data") or "")
    sender = callback_query.get("from") or {}
    telegram_user_id = str(sender.get("id") or "")
    message = callback_query.get("message") or {}
    chat = message.get("chat") or {}
    chat_id = str(chat.get("id") or "")
    message_id = message.get("message_id")

    if not data.startswith("reminder:") or not callback_query_id:
        if callback_query_id:
            await telegram_client.answer_callback_query(callback_query_id)
        return

    parts = data.split(":", maxsplit=2)
    if len(parts) != 3:
        await telegram_client.answer_callback_query(
            callback_query_id, "Не удалось обработать кнопку"
        )
        return

    _, action, reminder_id = parts
    if action == "ok":
        await telegram_client.answer_callback_query(callback_query_id)
        if chat_id and message_id:
            await remove_callback_buttons(chat_id, int(message_id))
        return

    if action != "snooze5":
        await telegram_client.answer_callback_query(callback_query_id, "Неизвестное действие")
        return

    result = await session.execute(
        select(Reminder)
        .join(User, User.id == Reminder.user_id)
        .where(Reminder.id == reminder_id, User.telegram_user_id == telegram_user_id)
    )
    reminder = result.scalar_one_or_none()
    if reminder is None:
        await telegram_client.answer_callback_query(callback_query_id, "Напоминание не найдено")
        return

    existing_snooze_result = await session.execute(
        select(Reminder)
        .where(
            Reminder.source_message_id == reminder.id,
            Reminder.status == ReminderStatus.pending.value,
        )
        .limit(1)
    )
    if existing_snooze_result.scalar_one_or_none() is None:
        snoozed_reminder = Reminder(
            user_id=reminder.user_id,
            text=reminder.text,
            due_at=datetime.now(timezone.utc) + timedelta(minutes=5),
            source_message_id=reminder.id,
        )
        session.add(snoozed_reminder)
        await session.commit()

    await telegram_client.answer_callback_query(callback_query_id, "Перенесено на 5 минут")
    if chat_id and message_id:
        await remove_callback_buttons(chat_id, int(message_id))


async def remove_callback_buttons(chat_id: str, message_id: int) -> None:
    try:
        await telegram_client.remove_message_buttons(chat_id, message_id)
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "Failed to remove Telegram inline keyboard: status=%s body=%s",
            exc.response.status_code,
            exc.response.text,
        )
