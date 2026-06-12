from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DelegatedTask
from app.services.schemas import IntentResult


class WebTaskService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def latest_open(self, user_id: str, thread_id: str) -> DelegatedTask | None:
        result = await self.session.execute(
            select(DelegatedTask)
            .where(
                DelegatedTask.user_id == user_id,
                DelegatedTask.thread_id == thread_id,
                DelegatedTask.status == "open",
            )
            .order_by(DelegatedTask.updated_at.desc(), DelegatedTask.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def create_or_update(
        self,
        user_id: str,
        thread_id: str,
        intent: IntentResult,
        raw_text: str,
    ) -> tuple[DelegatedTask, str]:
        task = await self.latest_open(user_id, thread_id)
        context = intent.extracted_context or {}

        if task and intent.intent == "web_search_update":
            task.objective = intent.task_text or task.objective
            task.context = {**(task.context or {}), **context}
            task.updated_at = func.now()
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
        return task, message

    async def set_result(self, task: DelegatedTask, result: dict[str, Any]) -> None:
        task.result = result
        task.updated_at = func.now()
        await self.session.flush()
