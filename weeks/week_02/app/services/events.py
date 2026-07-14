from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Event


class EventService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_events(self) -> list[Event]:
        result = await self._session.scalars(select(Event).order_by(Event.starts_at))

        return list(result.all())
