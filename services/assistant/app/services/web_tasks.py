from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DelegatedTask
from app.services.schemas import IntentResult


class WebTaskService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_or_update(
        self,
        user_id: str,
        thread_id: str,
        intent: IntentResult,
        raw_text: str,
    ) -> dict:
        result = await self.session.execute(
            select(DelegatedTask)
            .where(DelegatedTask.user_id == user_id, DelegatedTask.thread_id == thread_id)
            .order_by(DelegatedTask.created_at.desc())
            .limit(1)
        )
        task = result.scalar_one_or_none()
        context = intent.extracted_context or {}

        if task and task.status == "open":
            task.objective = intent.task_text or raw_text
            task.context = {**(task.context or {}), **context}
            message = "Обновил задачу поиска с учетом уточнения. Запускаю поиск."
        else:
            task = DelegatedTask(
                user_id=user_id,
                thread_id=thread_id,
                objective=intent.task_text or raw_text,
                context=context,
            )
            self.session.add(task)
            message = "Принял задачу. Запускаю поиск и сравнение вариантов."

        await self.session.flush()
        return {
            "task_id": task.id,
            "objective": task.objective,
            "context": task.context,
            "message": message,
        }

