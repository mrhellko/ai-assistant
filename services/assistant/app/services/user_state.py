from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Message, Thread, User


class UserState:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_or_create_user(
        self, telegram_user_id: str, display_name: str | None, timezone: str
    ) -> User:
        result = await self.session.execute(
            select(User).where(User.telegram_user_id == telegram_user_id)
        )
        user = result.scalar_one_or_none()
        if user:
            if display_name and user.display_name != display_name:
                user.display_name = display_name
            if timezone and user.timezone != timezone:
                user.timezone = timezone
            return user

        user = User(
            telegram_user_id=telegram_user_id,
            display_name=display_name,
            timezone=timezone,
        )
        self.session.add(user)
        await self.session.flush()
        return user

    async def get_active_thread(self, user: User, topic_key: str = "general") -> Thread:
        result = await self.session.execute(
            select(Thread)
            .where(
                Thread.user_id == user.id,
                Thread.topic_key == topic_key,
                Thread.is_active.is_(True),
            )
            .order_by(Thread.updated_at.desc())
        )
        thread = result.scalar_one_or_none()
        if thread:
            return thread

        thread = Thread(user_id=user.id, topic_key=topic_key, title=topic_key)
        self.session.add(thread)
        await self.session.flush()
        return thread

    async def start_new_thread(self, user: User, topic_key: str = "general") -> Thread:
        await self.session.execute(
            update(Thread).where(Thread.user_id == user.id).values(is_active=False)
        )
        thread = Thread(user_id=user.id, topic_key=topic_key, title=topic_key)
        self.session.add(thread)
        await self.session.flush()
        return thread

    async def add_message(
        self, thread: Thread, role: str, content: str, payload: dict | None = None
    ) -> Message:
        message = Message(
            thread_id=thread.id,
            role=role,
            content=content,
            payload=payload or {},
        )
        self.session.add(message)
        await self.session.flush()
        return message

    async def recent_context(self, thread: Thread, limit: int = 12) -> list[dict[str, str]]:
        result = await self.session.execute(
            select(Message)
            .where(Message.thread_id == thread.id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        messages = list(reversed(result.scalars().all()))
        return [{"role": item.role, "content": item.content} for item in messages]
