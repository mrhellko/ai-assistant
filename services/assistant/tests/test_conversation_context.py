import pytest

from app.db.models import DelegatedTask, Thread, UserIntentState
from app.services.conversation_context import (
    build_pending_intent_context,
    build_route_context,
    delegated_task_reference,
)


class FakeUserState:
    async def recent_context(self, thread: Thread, limit: int) -> list[dict[str, str]]:
        return [
            {"role": "user", "content": "найди пруток 20мм"},
            {"role": "assistant", "content": "Ищу варианты."},
        ]


class FakeWebTasks:
    async def latest_open(self, user_id: str, thread_id: str) -> DelegatedTask:
        return DelegatedTask(
            user_id=user_id,
            thread_id=thread_id,
            objective="найти пруток 20мм",
            context={"item": "пруток", "diameter": "20мм"},
        )


def test_build_pending_intent_context_uses_stored_clarification() -> None:
    state = UserIntentState(
        user_id="user-1",
        intent="reminder_need_info",
        payload={
            "pending_user_text": "напомни купить пруток",
            "clarification_question": "Когда?",
        },
    )

    context = build_pending_intent_context(state, "в понедельник")

    assert context == [
        {"role": "user", "content": "напомни купить пруток"},
        {"role": "assistant", "content": "Когда?"},
        {"role": "user", "content": "в понедельник"},
    ]


def test_delegated_task_reference_includes_objective_and_context() -> None:
    task = DelegatedTask(
        user_id="user-1",
        thread_id="thread-1",
        objective="найти пруток 20мм",
        context={"item": "пруток", "diameter": "20мм"},
    )

    reference = delegated_task_reference(task)

    assert reference is not None
    assert "Активная задача: найти пруток 20мм" in reference
    assert "diameter" in reference


def test_delegated_task_reference_includes_last_result_excerpt() -> None:
    task = DelegatedTask(
        user_id="user-1",
        thread_id="thread-1",
        objective="найти пруток 20мм",
        result={
            "status": "completed",
            "text": "Вариант 2: Ozon, 1200 руб., доставка завтра, https://example.test",
        },
    )

    reference = delegated_task_reference(task)

    assert reference is not None
    assert "Последний результат задачи" in reference
    assert "Ozon" in reference


@pytest.mark.asyncio
async def test_build_route_context_adds_thread_history_and_active_task() -> None:
    thread = Thread(
        id="thread-1",
        user_id="user-1",
        title="general",
        topic_key="general",
        summary="Пользователь ищет металлический пруток.",
    )

    context = await build_route_context(
        state=FakeUserState(),
        web_tasks=FakeWebTasks(),
        user_id="user-1",
        thread=thread,
        active_intent_state=None,
        current_text="напомни купить его в понедельник",
    )

    assert context[0]["role"] == "assistant"
    assert "Контекст ниже нужен только для понимания текущей темы" in context[0]["content"]
    assert context[1] == {
        "role": "assistant",
        "content": "Краткий контекст текущей темы: Пользователь ищет металлический пруток.",
    }
    assert {"role": "user", "content": "найди пруток 20мм"} in context
    assert any("Активная задача: найти пруток 20мм" in item["content"] for item in context)
    assert context[-1] == {"role": "user", "content": "напомни купить его в понедельник"}
