from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Reminder


class ReminderService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        user_id: str,
        text: str,
        due_at: datetime,
        source_message_id: str | None = None,
    ) -> Reminder:
        reminder = Reminder(
            user_id=user_id,
            text=text,
            due_at=due_at,
            source_message_id=source_message_id,
        )
        self.session.add(reminder)
        await self.session.flush()
        return reminder

