from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import DATABASE_URL
from app.infra.postgres.postgres import PostgresClient

postgres = PostgresClient(DATABASE_URL)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with postgres.session() as session:
        yield session
