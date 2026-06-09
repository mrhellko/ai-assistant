from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://assistant:assistant@postgres:5432/assistant"
    assistant_public_base_url: str = "http://localhost:8000"
    assistant_secret: str = "change-me"
    app_timezone: str = "Europe/Moscow"

    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"

    telegram_bot_token: str | None = None
    telegram_webhook_secret: str | None = None

    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str | None = None


settings = Settings()
