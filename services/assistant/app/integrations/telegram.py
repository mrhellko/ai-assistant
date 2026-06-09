from typing import Any

import httpx

from app.core.settings import settings


class TelegramClient:
    def __init__(self) -> None:
        self.token = settings.telegram_bot_token

    @property
    def is_configured(self) -> bool:
        return bool(self.token and self.token != "change-me")

    async def send_message(
        self,
        chat_id: str,
        text: str,
        reply_markup: dict[str, Any] | None = None,
    ) -> None:
        if not self.is_configured:
            return
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()

    async def remove_message_buttons(self, chat_id: str, message_id: int) -> None:
        if not self.is_configured:
            return
        url = f"https://api.telegram.org/bot{self.token}/editMessageReplyMarkup"
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "message_id": message_id,
        }
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()

    async def answer_callback_query(self, callback_query_id: str, text: str | None = None) -> None:
        if not self.is_configured:
            return
        url = f"https://api.telegram.org/bot{self.token}/answerCallbackQuery"
        payload: dict[str, Any] = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()


telegram_client = TelegramClient()
