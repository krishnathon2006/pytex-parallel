from app.exceptions import EventNotFoundError
from app.infra.postgres.postgres import PostgresClient
from app.infra.postgres.repositories.events import EventRepository
from app.infra.redis.caches import EventCache
from app.models import Event
from app.schemas import EventRead


class EventService:
    def __init__(self, postgres: PostgresClient, event_cache: EventCache) -> None:
        self._postgres = postgres
        self._event_cache = event_cache

    async def _load_from_db(self, event_id: int) -> EventRead | None:
        async with self._postgres.session() as session:
            event: Event | None = await EventRepository(session).get(event_id)

            if not event:
                return None

            return EventRead.model_validate(event)

    async def get_event(self, event_id: int) -> EventRead:
        value = await self._event_cache.get_or_load(
            event_id, lambda: self._load_from_db(event_id)
        )

        if not value:
            raise EventNotFoundError

        return value

    async def list_events(self) -> list[Event]:
        async with self._postgres.session() as session:
            return await EventRepository(session).list_ordered_by_start()
