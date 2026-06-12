from urllib.parse import urlencode

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import settings
from app.db.models import IntegrationToken
from app.services.schemas import IntentResult


class GoogleCalendar:
    scopes = [
        "https://www.googleapis.com/auth/calendar.events",
        "https://www.googleapis.com/auth/contacts.readonly",
    ]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def has_credentials(self, user_id: str) -> bool:
        result = await self.session.execute(
            select(IntegrationToken).where(
                IntegrationToken.user_id == user_id,
                IntegrationToken.provider == "google",
            )
        )
        return result.scalar_one_or_none() is not None

    def authorization_url(self, user_id: str) -> str:
        params = {
            "client_id": settings.google_client_id or "",
            "redirect_uri": settings.google_redirect_uri or "",
            "response_type": "code",
            "scope": " ".join(self.scopes),
            "access_type": "offline",
            "prompt": "consent",
            "state": user_id,
        }
        return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)

    async def create_event(self, user_id: str, intent: IntentResult) -> dict:
        # OAuth token exchange and Google API call are wired in the OAuth endpoint next.
        return {
            "status": "stub",
            "summary": intent.event_title,
            "start": intent.event_start.isoformat() if intent.event_start else None,
            "end": intent.event_end.isoformat() if intent.event_end else None,
            "attendees": intent.attendees,
        }
