import httpx

from app.core.settings import settings


async def send_outbound_event(payload: dict) -> None:
    if not settings.n8n_outbound_webhook_url:
        return
    async with httpx.AsyncClient(timeout=15) as client:
        await client.post(settings.n8n_outbound_webhook_url, json=payload)

