from app.infra.postgres.postgres import PostgresClient
from app.infra.postgres.repositories.events import EventRepository
from app.models import Event


class EventService:
    def __init__(self, postgres: PostgresClient) -> None:
        self._postgres = postgres

    async def list_events(self) -> list[Event]:
        async with self._postgres.session() as session:
            return await EventRepository(session).list_ordered_by_start()
