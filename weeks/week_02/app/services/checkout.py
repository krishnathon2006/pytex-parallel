import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

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
from app.infra.postgres.repositories.bookings import BookingRepository
from app.infra.postgres.repositories.event_seats import EventSeatRepository
from app.infra.postgres.repositories.events import EventRepository
from app.infra.postgres.repositories.seats import SeatRepository
from app.models import Booking, BookingStatus, Event, SeatStatus
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
            event = await EventRepository(session).get(event_id)
            if event is None:
                raise EventNotFoundError

            # Seats are locked in ascending id order, so two concurrent checkouts
            # over overlapping seats can never deadlock against each other.
            event_seats = await EventSeatRepository(session).lock_for_update(
                event_id, seat_ids
            )

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

            await BookingRepository(session).add(booking)

            for event_seat in event_seats:
                event_seat.booking_id = booking.id
                event_seat.status = SeatStatus.reserved
                event_seat.reserved_until = reserved_until

            seats_by_id = await SeatRepository(session).map_by_ids(seat_ids)

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

            protection_price = (
                protection_quote.price
                if protection_quote and protection_quote.available
                else None
            )

            async with self._postgres.transaction() as session:
                updated_rows = await BookingRepository(session).apply_quotes(
                    booking.id, payment_quote.commission, protection_price
                )
                if updated_rows == 0:
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
            await BookingRepository(session).mark_cancelled(booking_id)

            # Lock seats in the same ascending-id order as the reservation query,
            # otherwise this bulk release can deadlock with a concurrent checkout.
            event_seat_repository = EventSeatRepository(session)
            locked_seat_ids = await event_seat_repository.lock_ids_for_booking(
                booking_id
            )
            if locked_seat_ids:
                await event_seat_repository.release(locked_seat_ids)
