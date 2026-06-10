from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.settings import settings
from app.db import models
from app.services.intent_definitions import INTENT_DEFINITIONS

engine = create_async_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def create_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)
        await seed_intent_definitions(conn)


async def seed_intent_definitions(conn) -> None:
    statement = insert(models.IntentDefinition).values(INTENT_DEFINITIONS)
    statement = statement.on_conflict_do_update(
        index_elements=[models.IntentDefinition.name],
        set_={
            "description": statement.excluded.description,
            "details": statement.excluded.details,
            "is_active": True,
            "sort_order": statement.excluded.sort_order,
        },
    )
    await conn.execute(statement)


async def get_session():
    async with SessionLocal() as session:
        yield session
