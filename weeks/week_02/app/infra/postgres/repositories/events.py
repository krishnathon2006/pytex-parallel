from sqlalchemy import select

from app.infra.postgres.repositories.base import BaseRepository
from app.models import Event


class EventRepository(BaseRepository):
    async def get(self, event_id: int) -> Event | None:
        return await self._session.get(Event, event_id)

    async def list_ordered_by_start(self) -> list[Event]:
        result = await self._session.scalars(select(Event).order_by(Event.starts_at))

        return list(result.all())
