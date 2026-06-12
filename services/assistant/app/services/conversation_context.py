from app.db.models import DelegatedTask, Thread, UserIntentState
from app.services.reference_resolver import task_result_text
from app.services.user_state import UserState
from app.services.web_tasks import WebTaskService


THREAD_CONTEXT_LIMIT = 4


async def build_route_context(
    *,
    state: UserState,
    web_tasks: WebTaskService,
    user_id: str,
    thread: Thread,
    active_intent_state: UserIntentState | None,
    current_text: str,
) -> list[dict[str, str]]:
    if active_intent_state and active_intent_state.intent == "reminder_need_info":
        pending_context = build_pending_intent_context(active_intent_state, current_text)
        if pending_context:
            return pending_context

    context = [
        {
            "role": "assistant",
            "content": (
                "Контекст ниже нужен только для понимания текущей темы и явных ссылок "
                "вроде 'его', 'этот вариант', 'ту встречу'. Не создавай детали "
                "напоминаний из старой истории без явной ссылки пользователя."
            ),
        }
    ]
    context.extend(thread_context_messages(thread))
    context.extend(await state.recent_context(thread, limit=THREAD_CONTEXT_LIMIT))

    active_task = await web_tasks.latest_open(user_id, thread.id)
    task_reference = delegated_task_reference(active_task)
    if task_reference:
        context.append({"role": "assistant", "content": task_reference})

    context.append({"role": "user", "content": current_text})
    return compact_route_context(context)


def build_pending_intent_context(
    active_intent_state: UserIntentState,
    current_text: str,
) -> list[dict[str, str]]:
    payload = active_intent_state.payload or {}
    context_messages = normalized_context_messages(payload)
    if context_messages:
        return [*context_messages, {"role": "user", "content": current_text}]

    pending_user_text = payload.get("pending_user_text")
    clarification_question = payload.get("clarification_question")
    if (
        isinstance(pending_user_text, str)
        and pending_user_text.strip()
        and isinstance(clarification_question, str)
        and clarification_question.strip()
    ):
        return [
            {"role": "user", "content": pending_user_text},
            {"role": "assistant", "content": clarification_question},
            {"role": "user", "content": current_text},
        ]
    return []


def thread_context_messages(thread: Thread) -> list[dict[str, str]]:
    if not thread.summary or not thread.summary.strip():
        return []
    return [
        {
            "role": "assistant",
            "content": f"Краткий контекст текущей темы: {thread.summary.strip()}",
        }
    ]


def delegated_task_reference(task: DelegatedTask | None) -> str | None:
    if not task:
        return None

    parts = [f"Активная задача: {task.objective}"]
    context = task.context or {}
    if context:
        parts.append(f"Структурированный контекст задачи: {context}")
    result_text = task_result_text(task)
    if result_text:
        parts.append(f"Последний результат задачи: {result_text}")
    return "\n".join(parts)


def compact_route_context(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    compacted: list[dict[str, str]] = []
    for message in messages:
        role = message.get("role")
        content = message.get("content")
        if role not in {"user", "assistant"} or not isinstance(content, str) or not content.strip():
            continue
        compacted.append({"role": role, "content": content.strip()})
    return compacted


def normalized_context_messages(payload: dict) -> list[dict[str, str]]:
    raw_messages = payload.get("context_messages")
    if not isinstance(raw_messages, list):
        return []

    messages: list[dict[str, str]] = []
    for item in raw_messages:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = item.get("content")
        if role in {"user", "assistant"} and isinstance(content, str) and content.strip():
            messages.append({"role": role, "content": content.strip()})
    return messages
