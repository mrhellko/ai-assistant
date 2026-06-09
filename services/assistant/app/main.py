from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.oauth import router as oauth_router
from app.api.telegram import router as telegram_router
from app.core.settings import settings
from app.db.session import create_db
from app.scheduler.reminders import reminder_loop


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_db()
    task = reminder_loop.start()
    yield
    task.cancel()


app = FastAPI(title="AI Assistant", version="0.1.0", lifespan=lifespan)
app.include_router(health_router)
app.include_router(oauth_router, prefix="/api/oauth", tags=["oauth"])
app.include_router(telegram_router, prefix="/api/telegram", tags=["telegram"])


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": "assistant", "timezone": settings.app_timezone}
