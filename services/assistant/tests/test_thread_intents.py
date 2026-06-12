from app.services.assistant import thread_reset_reply
from app.services.schemas import IntentResult


def test_intent_result_accepts_thread_new() -> None:
    result = IntentResult(intent="thread_new")

    assert result.intent == "thread_new"


def test_intent_result_accepts_thread_forget() -> None:
    result = IntentResult(intent="thread_forget")

    assert result.intent == "thread_forget"


def test_thread_reset_reply_for_new_dialog() -> None:
    assert thread_reset_reply("thread_new") == "Ок, начал новый диалог."


def test_thread_reset_reply_for_forget_topic() -> None:
    assert (
        thread_reset_reply("thread_forget")
        == "Ок, текущую тему больше не учитываю. Начинаем с чистого контекста."
    )
