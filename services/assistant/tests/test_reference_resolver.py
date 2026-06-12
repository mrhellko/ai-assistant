import pytest

from app.db.models import DelegatedTask
from app.services.reference_resolver import (
    TASK_RESULT_TEXT_LIMIT,
    TaskReferenceResolver,
    task_payload,
    task_result_text,
)


class FakeResponse:
    output_text = '{"resolved_reminder_text": "купить пруток 20мм"}'


class FakeResponses:
    async def create(self, **kwargs):
        return FakeResponse()


class FakeClient:
    def __init__(self) -> None:
        self.responses = FakeResponses()


@pytest.mark.asyncio
async def test_reference_resolver_returns_original_without_client() -> None:
    resolver = TaskReferenceResolver(client=None, model="test-model")
    task = DelegatedTask(user_id="user-1", thread_id="thread-1", objective="найти пруток 20мм")

    resolved = await resolver.resolve(
        current_text="напомни купить его в понедельник",
        reminder_text="купить его",
        active_task=task,
    )

    assert resolved == "купить его"


@pytest.mark.asyncio
async def test_reference_resolver_uses_llm_result() -> None:
    resolver = TaskReferenceResolver(client=FakeClient(), model="test-model")
    task = DelegatedTask(user_id="user-1", thread_id="thread-1", objective="найти пруток 20мм")

    resolved = await resolver.resolve(
        current_text="напомни купить его в понедельник",
        reminder_text="купить его",
        active_task=task,
    )

    assert resolved == "купить пруток 20мм"


def test_task_payload_contains_objective_and_context() -> None:
    task = DelegatedTask(
        user_id="user-1",
        thread_id="thread-1",
        objective="найти пруток 20мм",
        context={"diameter": "20мм"},
    )

    assert task_payload(task) == {
        "objective": "найти пруток 20мм",
        "context": {"diameter": "20мм"},
    }


def test_task_payload_includes_bounded_search_result_text() -> None:
    task = DelegatedTask(
        user_id="user-1",
        thread_id="thread-1",
        objective="найти пруток 20мм",
        context={"diameter": "20мм"},
        result={
            "status": "completed",
            "text": "Вариант 1: Ozon, 1200 руб., доставка завтра, https://example.test",
        },
    )

    assert task_payload(task) == {
        "objective": "найти пруток 20мм",
        "context": {"diameter": "20мм"},
        "result_text": "Вариант 1: Ozon, 1200 руб., доставка завтра, https://example.test",
    }


def test_task_result_text_is_limited() -> None:
    task = DelegatedTask(
        user_id="user-1",
        thread_id="thread-1",
        objective="найти пруток 20мм",
        result={"text": "x" * (TASK_RESULT_TEXT_LIMIT + 50)},
    )

    result_text = task_result_text(task)

    assert result_text is not None
    assert len(result_text) == TASK_RESULT_TEXT_LIMIT + 3
    assert result_text.endswith("...")
