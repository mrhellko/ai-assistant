from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import settings
from app.db.session import get_session
from app.services.assistant import AssistantService
from app.services.schemas import IncomingTelegramMessage, AssistantResponse

router = APIRouter()


def verify_secret(x_assistant_secret: str | None = Header(default=None)) -> None:
    if settings.assistant_secret != "change-me" and x_assistant_secret != settings.assistant_secret:
        raise HTTPException(status_code=401, detail="invalid assistant secret")


@router.post("/telegram-message", response_model=AssistantResponse)
async def telegram_message(
    payload: IncomingTelegramMessage,
    _: None = Depends(verify_secret),
    session: AsyncSession = Depends(get_session),
) -> AssistantResponse:
    service = AssistantService(session)
    return await service.handle_telegram_message(payload)

