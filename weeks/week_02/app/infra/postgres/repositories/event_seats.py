from datetime import datetime

from sqlalchemy import and_, func, select, update

from app.infra.postgres.repositories.base import BaseRepository
from app.models import EventSeat, SeatStatus


class EventSeatRepository(BaseRepository):
    async def lock_for_update(
        self, event_id: int, seat_ids: list[int]
    ) -> list[EventSeat]:
        statement = (
            select(EventSeat)
            .where(EventSeat.event_id == event_id, EventSeat.seat_id.in_(seat_ids))
            .order_by(EventSeat.id)
            .with_for_update()
        )

        result = await self._session.scalars(statement)

        return list(result.all())

    async def lock_ids_for_booking(self, booking_id: int) -> list[int]:
        result = await self._session.scalars(
            select(EventSeat.id)
            .where(EventSeat.booking_id == booking_id)
            .order_by(EventSeat.id)
            .with_for_update()
        )

        return list(result.all())

    async def release(self, event_seat_ids: list[int]) -> None:
        await self._session.execute(
            update(EventSeat)
            .where(EventSeat.id.in_(event_seat_ids))
            .values(
                status=SeatStatus.available,
                reserved_until=None,
                booking_id=None,
            )
        )

    async def count_sold(self, event_id: int) -> int:
        sold = await self._session.scalar(
            select(func.count())
            .select_from(EventSeat)
            .where(
                EventSeat.event_id == event_id,
                EventSeat.status == SeatStatus.sold,
            )
        )

        return sold or 0

    async def occupancy_counts(
        self, event_id: int, now: datetime
    ) -> tuple[int, int, int]:
        """Возвращает (всего, забронировано, продано). Истекшая бронь местом
        не считается — те же правила, что и при бронировании."""
        reserved_active = and_(
            EventSeat.status == SeatStatus.reserved,
            EventSeat.reserved_until > now,
        )

        total, reserved, sold = (
            await self._session.execute(
                select(
                    func.count(),
                    func.count().filter(reserved_active),
                    func.count().filter(EventSeat.status == SeatStatus.sold),
                )
                .select_from(EventSeat)
                .where(EventSeat.event_id == event_id)
            )
        ).one()

        return total, reserved, sold
