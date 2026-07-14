import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from app.config import BOOKING_TTL_MINUTES
from app.exceptions import (
    DuplicateSeatError,
    EventNotFoundError,
    SeatsNotFoundError,
    SeatsUnavailableError,
)
from app.infra.clients.payment import PaymentClient
from app.infra.clients.protection import ProtectionClient
from app.infra.postgres.postgres import PostgresClient
from app.models import Booking, BookingStatus, Event, EventSeat, Seat, SeatStatus
from app.schemas import PaymentQuote, ProtectionQuote
from app.utils import row_label

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class CheckoutResult:
    booking: Booking
    event: Event
    seats: list[dict[str, str | int]]
    payment: PaymentQuote
    protection: ProtectionQuote | None


class CheckoutService:
    def __init__(
        self,
        postgres: PostgresClient,
        payment_client: PaymentClient,
        protection_client: ProtectionClient,
    ) -> None:
        self._postgres = postgres
        self._payment_client = payment_client
        self._protection_client = protection_client

    async def prepare_checkout(
        self, event_id: int, seat_ids: list[int], user_id: int
    ) -> CheckoutResult:
        if len(seat_ids) != len(set(seat_ids)):
            raise DuplicateSeatError("Seats must be unique")

        async with self._postgres.transaction() as session:
            event = await session.get(Event, event_id)
            if event is None:
                raise EventNotFoundError

            statement = (
                select(EventSeat)
                .where(EventSeat.event_id == event_id, EventSeat.seat_id.in_(seat_ids))
                .order_by(EventSeat.id)
                .with_for_update()
            )

            result = await session.scalars(statement)
            event_seats = list(result.all())

            if len(event_seats) != len(seat_ids):
                raise SeatsNotFoundError("Seats not found")

            now = datetime.now(UTC)

            for event_seat in event_seats:
                reservation_is_orphaned = (
                    event_seat.status == SeatStatus.reserved
                    and event_seat.booking_id is None
                )

                reservation_has_expired = (
                    event_seat.status == SeatStatus.reserved
                    and event_seat.reserved_until is not None
                    and event_seat.reserved_until <= now
                )

                seat_is_available = (
                    event_seat.status == SeatStatus.available
                    or reservation_is_orphaned
                    or reservation_has_expired
                )

                if not seat_is_available:
                    raise SeatsUnavailableError("Seats are unavailable")

            reserved_until = now + timedelta(minutes=BOOKING_TTL_MINUTES)
            base_amount = sum(event_seat.price for event_seat in event_seats)
            booking = Booking(
                event_id=event_id,
                user_id=user_id,
                amount=base_amount,
                payment_commission=0,
                protection_price=None,
                with_protection=False,
                status=BookingStatus.pending_payment,
                reserved_until=reserved_until,
            )

            session.add(booking)

            await session.flush()

            for event_seat in event_seats:
                event_seat.booking_id = booking.id
                event_seat.status = SeatStatus.reserved
                event_seat.reserved_until = reserved_until

            seat_rows = await session.scalars(select(Seat).where(Seat.id.in_(seat_ids)))
            seats_by_id = {seat.id: seat for seat in seat_rows}

            seat_details: list[dict[str, int | str]] = []
            for event_seat in event_seats:
                seat = seats_by_id[event_seat.seat_id]
                seat_details.append(
                    {
                        "seat_id": seat.id,
                        "sector": seat.sector,
                        "row": row_label(seat.row),
                        "number": seat.number,
                        "price": event_seat.price,
                    }
                )

        protection_task = asyncio.create_task(
            self._protection_client.calculate(
                booking_id=booking.id,
                ticket_amount=booking.amount,
                event_category=event.category,
                event_starts_at=event.starts_at,
            )
        )
        try:
            payment_quote = await self._payment_client.calculate(
                booking.id, booking.amount
            )
            protection_quote = await self._collect_protection_quote(
                protection_task, booking.id
            )

            async with self._postgres.transaction() as session:
                values: dict[str, int] = {
                    "payment_commission": payment_quote.commission
                }
                if protection_quote and protection_quote.available:
                    values["protection_price"] = protection_quote.price
                update_result = await session.execute(
                    update(Booking)
                    .where(
                        Booking.id == booking.id,
                        Booking.status == BookingStatus.pending_payment,
                    )
                    .values(**values)
                )
                if update_result.rowcount == 0:
                    raise SeatsUnavailableError("Reservation expired during checkout")
        except Exception:
            logger.warning(
                "Checkout failed after reservation, releasing booking %s", booking.id
            )
            protection_task.cancel()
            await asyncio.gather(protection_task, return_exceptions=True)
            await self._release_booking(booking.id)
            raise

        return CheckoutResult(
            booking=booking,
            event=event,
            seats=seat_details,
            payment=payment_quote,
            protection=protection_quote,
        )

    async def _collect_protection_quote(
        self, protection_task: asyncio.Task[ProtectionQuote | None], booking_id: int
    ) -> ProtectionQuote | None:
        try:
            return await protection_task
        except Exception:
            logger.exception(
                "Protection task failed unexpectedly for booking %s", booking_id
            )
            return None

    async def _release_booking(self, booking_id: int) -> None:
        async with self._postgres.transaction() as session:
            await session.execute(
                update(Booking)
                .where(Booking.id == booking_id)
                .values(status=BookingStatus.cancelled)
            )
            # Lock seats in the same ascending-id order as the reservation query,
            # otherwise this bulk release can deadlock with a concurrent checkout.
            locked_seat_ids = list(
                await session.scalars(
                    select(EventSeat.id)
                    .where(EventSeat.booking_id == booking_id)
                    .order_by(EventSeat.id)
                    .with_for_update()
                )
            )
            if locked_seat_ids:
                await session.execute(
                    update(EventSeat)
                    .where(EventSeat.id.in_(locked_seat_ids))
                    .values(
                        status=SeatStatus.available,
                        reserved_until=None,
                        booking_id=None,
                    )
                )
