import pytest

from app.api.telegram import handle_location_command, normalize_location, parse_location_command


class FakeUser:
    def __init__(self, location: str) -> None:
        self.location = location


class FakeSession:
    def __init__(self) -> None:
        self.committed = False

    async def commit(self) -> None:
        self.committed = True


def test_parse_location_command_returns_normalized_city() -> None:
    assert parse_location_command("/location   Санкт   Петербург  ") == "Санкт Петербург"


def test_parse_location_command_supports_bot_suffix() -> None:
    assert parse_location_command("/location@assistant_bot Казань") == "Казань"


def test_parse_location_command_ignores_other_text() -> None:
    assert parse_location_command("найди аквапарк") is None


def test_parse_location_command_requires_argument() -> None:
    assert parse_location_command("/location") == ""


def test_normalize_location_limits_length() -> None:
    assert len(normalize_location("x" * 300)) == 255


@pytest.mark.asyncio
async def test_handle_location_command_requires_city() -> None:
    response = await handle_location_command(
        session=FakeSession(),
        telegram_user_id="user-1",
        display_name=None,
        location="",
    )

    assert response == "Укажите город после команды, например: /location Москва"


@pytest.mark.asyncio
async def test_handle_location_command_saves_user_location(monkeypatch) -> None:
    session = FakeSession()
    calls = {}

    class FakeUserState:
        def __init__(self, session_arg) -> None:
            calls["session"] = session_arg

        async def update_location(self, **kwargs):
            calls["kwargs"] = kwargs
            return FakeUser(location=kwargs["location"])

    monkeypatch.setattr("app.api.telegram.UserState", FakeUserState)

    response = await handle_location_command(
        session=session,
        telegram_user_id="user-1",
        display_name="Test User",
        location="Екатеринбург",
    )

    assert response == "Готово. Буду учитывать город при поиске: Екатеринбург"
    assert session.committed is True
    assert calls["session"] is session
    assert calls["kwargs"]["telegram_user_id"] == "user-1"
    assert calls["kwargs"]["display_name"] == "Test User"
    assert calls["kwargs"]["location"] == "Екатеринбург"
