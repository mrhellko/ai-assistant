import asyncio
from datetime import datetime, timezone

from sqlalchemy import select

from app.db.models import Reminder, ReminderStatus, User
from app.db.session import SessionLocal
from app.integrations.telegram import telegram_client


class ReminderLoop:
    def start(self) -> asyncio.Task:
        return asyncio.create_task(self._run())

    async def _run(self) -> None:
        while True:
            await self._tick()
            await asyncio.sleep(20)

    async def _tick(self) -> None:
        async with SessionLocal() as session:
            result = await session.execute(
                select(Reminder, User)
                .join(User, User.id == Reminder.user_id)
                .where(
                    Reminder.status == ReminderStatus.pending.value,
                    Reminder.due_at <= datetime.now(timezone.utc),
                )
                .limit(50)
            )
            rows = result.all()
            for reminder, user in rows:
                await telegram_client.send_message(user.telegram_user_id, reminder.text)
                reminder.status = ReminderStatus.sent.value
            await session.commit()


reminder_loop = ReminderLoop()
