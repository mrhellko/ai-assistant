import pytest

from app.db.models import DelegatedTask
from app.services.assistant import format_web_search_reply
from app.services.schemas import IntentResult
from app.services.web_search import WEB_SEARCH_SYSTEM_PROMPT, WebSearchRunner, search_prompt
from app.services.web_tasks import WebTaskService


class FakeResponse:
    output_text = "Вариант 1: пример результата."


class FakeResponses:
    def __init__(self) -> None:
        self.kwargs = None

    async def create(self, **kwargs):
        self.kwargs = kwargs
        return FakeResponse()


class FakeClient:
    def __init__(self) -> None:
        self.responses = FakeResponses()


class FakeSession:
    def __init__(self) -> None:
        self.added = []
        self.flushed = False

    def add(self, item) -> None:
        self.added.append(item)

    async def flush(self) -> None:
        self.flushed = True


def make_intent(intent: str, task_text: str) -> IntentResult:
    return IntentResult(
        intent=intent,
        task_text=task_text,
        extracted_context={"length": "200мм"},
    )


def latest_open_result(task: DelegatedTask):
    async def latest_open(*_args):
        return task

    return latest_open


def test_search_prompt_contains_objective_location_and_context() -> None:
    task = DelegatedTask(
        user_id="user-1",
        thread_id="thread-1",
        objective="найти пруток 20мм",
        context={"length": "короче"},
    )

    prompt = search_prompt(task, "Санкт-Петербург")

    assert "Задача: найти пруток 20мм" in prompt
    assert "Город пользователя: Санкт-Петербург" in prompt
    assert "ищи варианты для города пользователя" in prompt
    assert "length" in prompt
    assert "короче" in prompt


def test_web_search_prompt_prefers_retail_when_wholesale_is_not_requested() -> None:
    assert "розничный вариант" in WEB_SEARCH_SYSTEM_PROMPT
    assert "Оптовые поставщики допустимы" in WEB_SEARCH_SYSTEM_PROMPT


@pytest.mark.asyncio
async def test_web_search_runner_uses_responses_web_search_tool() -> None:
    client = FakeClient()
    runner = WebSearchRunner(client=client, model="test-model")
    task = DelegatedTask(
        user_id="user-1",
        thread_id="thread-1",
        objective="найти пруток 20мм",
        context={},
    )

    result = await runner.run(task, "Казань")

    assert result == {"status": "completed", "text": "Вариант 1: пример результата."}
    assert client.responses.kwargs["model"] == "test-model"
    expected_tools = [{"type": "web_search", "search_context_size": "low"}]
    assert client.responses.kwargs["tools"] == expected_tools
    assert client.responses.kwargs["tool_choice"] == "required"
    assert "Город пользователя: Казань" in client.responses.kwargs["input"][1]["content"]


@pytest.mark.asyncio
async def test_web_search_runner_reports_unavailable_without_client() -> None:
    runner = WebSearchRunner(client=None, model="test-model")
    runner.client = None
    task = DelegatedTask(
        user_id="user-1",
        thread_id="thread-1",
        objective="найти пруток 20мм",
    )

    result = await runner.run(task)

    assert result["status"] == "unavailable"
    assert "OPENAI_API_KEY" in result["text"]


def test_format_web_search_reply_falls_back_on_empty_result() -> None:
    reply = format_web_search_reply("Принял задачу.", {"status": "completed", "text": ""})

    assert reply == (
        "Принял задачу.\n\nПоиск завершился без результата. Попробуйте уточнить запрос."
    )


@pytest.mark.asyncio
async def test_web_search_intent_creates_new_task_even_when_open_task_exists() -> None:
    existing = DelegatedTask(
        user_id="user-1",
        thread_id="thread-1",
        objective="старый поиск",
        context={"old": True},
    )
    session = FakeSession()
    service = WebTaskService(session)
    service.latest_open = latest_open_result(existing)

    task, message = await service.create_or_update(
        "user-1",
        "thread-1",
        make_intent("web_search", "новый поиск"),
        "найди новый товар",
    )

    assert task is not existing
    assert task.objective == "новый поиск"
    assert existing.objective == "старый поиск"
    assert session.added == [task]
    assert session.flushed is True
    assert message == "Принял задачу. Запускаю поиск и сравнение вариантов."


@pytest.mark.asyncio
async def test_web_search_update_intent_updates_open_task() -> None:
    existing = DelegatedTask(
        user_id="user-1",
        thread_id="thread-1",
        objective="найти пруток 20мм",
        context={"diameter": "20мм"},
    )
    session = FakeSession()
    service = WebTaskService(session)
    service.latest_open = latest_open_result(existing)

    task, message = await service.create_or_update(
        "user-1",
        "thread-1",
        make_intent("web_search_update", "найти пруток 20мм длиной 200мм"),
        "давай длиной 200мм",
    )

    assert task is existing
    assert task.objective == "найти пруток 20мм длиной 200мм"
    assert task.context == {"diameter": "20мм", "length": "200мм"}
    assert session.added == []
    assert session.flushed is True
    assert message == "Обновил задачу поиска с учетом уточнения. Запускаю поиск."
