from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import UserIntentState


ACTIVE_STATUS = "active"
CLOSED_STATUS = "closed"


class IntentStateService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_active(self, user_id: str) -> UserIntentState | None:
        result = await self.session.execute(
            select(UserIntentState)
            .where(
                UserIntentState.user_id == user_id,
                UserIntentState.status == ACTIVE_STATUS,
            )
            .order_by(UserIntentState.updated_at.desc(), UserIntentState.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def set_active(
        self,
        user_id: str,
        thread_id: str | None,
        intent: str,
        payload: dict,
    ) -> UserIntentState:
        await self.clear_active(user_id)
        state = UserIntentState(
            user_id=user_id,
            thread_id=thread_id,
            intent=intent,
            status=ACTIVE_STATUS,
            payload=payload,
        )
        self.session.add(state)
        await self.session.flush()
        return state

    async def clear_active(self, user_id: str) -> None:
        await self.session.execute(
            update(UserIntentState)
            .where(
                UserIntentState.user_id == user_id,
                UserIntentState.status == ACTIVE_STATUS,
            )
            .values(status=CLOSED_STATUS)
        )
        await self.session.flush()
