from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Reminder, ReminderStatus


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

    async def list_future(
        self,
        user_id: str,
        page: int,
        page_size: int,
    ) -> tuple[list[Reminder], int]:
        now = datetime.now(timezone.utc)
        base_where = (
            Reminder.user_id == user_id,
            Reminder.status == ReminderStatus.pending.value,
            Reminder.due_at > now,
        )
        count_result = await self.session.execute(
            select(func.count()).select_from(Reminder).where(*base_where)
        )
        total = int(count_result.scalar_one())
        result = await self.session.execute(
            select(Reminder)
            .where(*base_where)
            .order_by(Reminder.due_at.asc(), Reminder.created_at.asc())
            .offset(max(page, 0) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), total

    async def list_history(
        self,
        user_id: str,
        page: int,
        page_size: int,
    ) -> tuple[list[Reminder], int]:
        count_result = await self.session.execute(
            select(func.count()).select_from(Reminder).where(Reminder.user_id == user_id)
        )
        total = int(count_result.scalar_one())
        result = await self.session.execute(
            select(Reminder)
            .where(Reminder.user_id == user_id)
            .order_by(Reminder.created_at.desc(), Reminder.due_at.desc())
            .offset(max(page, 0) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), total

    async def cancel_future(self, user_id: str, reminder_id: str) -> bool:
        result = await self.session.execute(
            select(Reminder).where(
                Reminder.id == reminder_id,
                Reminder.user_id == user_id,
                Reminder.status == ReminderStatus.pending.value,
                Reminder.due_at > datetime.now(timezone.utc),
            )
        )
        reminder = result.scalar_one_or_none()
        if reminder is None:
            return False
        reminder.status = ReminderStatus.cancelled.value
        await self.session.flush()
        return True
