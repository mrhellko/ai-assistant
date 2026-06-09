from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import settings
from app.db.models import IntegrationToken
from app.db.session import get_session

router = APIRouter()


@router.get("/google/callback")
async def google_callback(
    code: str = Query(...),
    state: str = Query(...),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(status_code=500, detail="Google OAuth is not configured")

    token = IntegrationToken(
        user_id=state,
        provider="google",
        encrypted_payload={"oauth_code": code, "status": "exchange_pending"},
    )
    session.add(token)
    await session.commit()
    return {"status": "connected"}

