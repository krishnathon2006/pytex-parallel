from sqlalchemy.dialects.postgresql import insert

from app.infra.postgres.repositories.base import BaseRepository
from app.models import EventView


class EventViewsRepository(BaseRepository):
    """Счетчики просмотров мероприятий."""

    async def add_views(self, views: dict[int, int]) -> None:
        """Прибавляет просмотры к счетчикам одним UPSERT-ом.

        sorted() фиксирует порядок блокировки строк: два параллельных сброса
        с пересекающимися мероприятиями иначе могут поймать deadlock.
        """
        if not views:
            return

        statement = insert(EventView).values(
            [
                {EventView.event_id: event_id, EventView.views_count: count}
                for event_id, count in sorted(views.items())
            ]
        )

        statement = statement.on_conflict_do_update(
            index_elements=[EventView.event_id],
            set_={
                EventView.views_count: EventView.views_count
                + statement.excluded.views_count
            },
        )
        await self._session.execute(statement)
