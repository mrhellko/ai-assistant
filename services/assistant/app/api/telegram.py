from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import settings
from app.db.session import get_session
from app.integrations.telegram import telegram_client
from app.services.assistant import AssistantService
from app.services.schemas import IncomingTelegramMessage

router = APIRouter()


def verify_telegram_secret(x_telegram_bot_api_secret_token: str | None = Header(default=None)) -> None:
    if settings.telegram_webhook_secret and settings.telegram_webhook_secret != "change-me":
        if x_telegram_bot_api_secret_token != settings.telegram_webhook_secret:
            raise HTTPException(status_code=401, detail="invalid telegram webhook secret")


@router.post("/webhook")
async def telegram_webhook(
    update: dict[str, Any],
    _: None = Depends(verify_telegram_secret),
    session: AsyncSession = Depends(get_session),
) -> dict[str, bool]:
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
