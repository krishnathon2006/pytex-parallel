from sqlalchemy import func, select, update

from app.infra.postgres.repositories.base import BaseRepository
from app.models import Booking, BookingStatus


class BookingRepository(BaseRepository):
    async def add(self, booking: Booking) -> None:
        self._session.add(booking)
        await self._session.flush()

    async def apply_quotes(
        self, booking_id: int, payment_commission: int, protection_price: int | None
    ) -> int:
        """Обновляет только бронь, которая все еще ждет оплаты, и возвращает
        количество затронутых строк — решение о просроченной броне за сервисом."""
        values: dict[str, int] = {"payment_commission": payment_commission}
        if protection_price is not None:
            values["protection_price"] = protection_price

        result = await self._session.execute(
            update(Booking)
            .where(
                Booking.id == booking_id,
                Booking.status == BookingStatus.pending_payment,
            )
            .values(**values)
        )

        return result.rowcount

    async def mark_cancelled(self, booking_id: int) -> None:
        await self._session.execute(
            update(Booking)
            .where(Booking.id == booking_id)
            .values(status=BookingStatus.cancelled)
        )

    async def sales_totals(self, event_id: int) -> tuple[int, int]:
        """Возвращает (количество оплаченных броней, выручку)."""
        paid_orders, revenue = (
            await self._session.execute(
                select(
                    func.count(),
                    func.coalesce(func.sum(Booking.amount), 0),
                )
                .select_from(Booking)
                .where(
                    Booking.event_id == event_id,
                    Booking.status == BookingStatus.paid,
                )
            )
        ).one()

        return paid_orders, revenue
