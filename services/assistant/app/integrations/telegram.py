from typing import Any

import httpx

from app.core.settings import settings


class TelegramClient:
    def __init__(self) -> None:
        self.token = settings.telegram_bot_token

    @property
    def is_configured(self) -> bool:
        return bool(self.token and self.token != "change-me")

    async def send_message(self, chat_id: str, text: str) -> None:
        if not self.is_configured:
            return
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()


telegram_client = TelegramClient()

