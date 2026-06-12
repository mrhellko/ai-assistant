import pytest

from app.agents.intent_manager import IntentManager
from app.services.schemas import IntentResult


class FakeResponse:
    def __init__(self, output_text: str) -> None:
        self.output_text = output_text


class FakeResponses:
    def __init__(self, outputs: list[str]) -> None:
        self.outputs = outputs
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        output = self.outputs.pop(0)
        return FakeResponse(output)


class FakeClient:
    def __init__(self, outputs: list[str]) -> None:
        self.responses = FakeResponses(outputs)


class FakeSession:
    async def execute(self, *_args, **_kwargs):
        raise AssertionError("session should not be used when system prompt is patched")


async def fake_system_prompt(_session) -> str:
    return "system prompt"


@pytest.mark.asyncio
async def test_route_retries_unknown_as_web_search_when_second_pass_finds_search(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = IntentManager()
    manager.client = FakeClient(
        [
            '{"intent":"unknown","reply":"Не понял"}',
            '{"intent":"web_search","task_text":"Найти аквапарки в Москве","extracted_context":{"object":"аквапарк","location":"Москва"}}',
        ]
    )
    monkeypatch.setattr(manager, "_system_prompt", fake_system_prompt)

    result = await manager.route(
        FakeSession(),
        "В какой аквапарк сходить?",
        "Europe/Moscow",
        [],
    )

    assert isinstance(result, IntentResult)
    assert result.intent == "web_search"
    assert result.task_text == "Найти аквапарки в Москве"
    assert len(manager.client.responses.calls) == 2
    assert (
        "Reconsider whether the user's message is actually a web-search task"
        in manager.client.responses.calls[1]["input"][0]["content"]
    )


@pytest.mark.asyncio
async def test_route_keeps_unknown_when_retry_still_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = IntentManager()
    manager.client = FakeClient(
        [
            '{"intent":"unknown","reply":"Не понял"}',
            '{"intent":"unknown","reply":"Не понял"}',
        ]
    )
    monkeypatch.setattr(manager, "_system_prompt", fake_system_prompt)

    result = await manager.route(
        FakeSession(),
        "Просто вопрос без поиска",
        "Europe/Moscow",
        [],
    )

    assert result.intent == "unknown"
    assert len(manager.client.responses.calls) == 2
