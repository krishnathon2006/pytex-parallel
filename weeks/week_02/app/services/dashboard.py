import asyncio
from datetime import UTC, datetime

from sqlalchemy import and_, func, select

from app.exceptions import AccessDeniedError, EventNotFoundError
from app.infra.postgres.postgres import PostgresClient
from app.models import Booking, BookingStatus, Event, EventSeat, SeatStatus
from app.schemas import EventDashboard, OccupancyDashboard, SalesDashboard


class DashboardService:
    def __init__(self, postgres: PostgresClient) -> None:
        self._postgres = postgres

    async def get_event_dashboard(
        self, event_id: int, organizer_id: int
    ) -> EventDashboard:
        async with self._postgres.session() as session:
            event = await session.get(Event, event_id)

        if event is None:
            raise EventNotFoundError
        if event.organizer_id != organizer_id:
            raise AccessDeniedError("Event belongs to another organizer")

        sales, occupancy = await asyncio.gather(
            self._load_sales(event_id),
            self._load_occupancy(event_id),
        )

        return EventDashboard(
            event_title=event.title,
            starts_at=event.starts_at,
            sales=sales,
            occupancy=occupancy,
        )

    async def _load_sales(self, event_id: int) -> SalesDashboard:
        async with self._postgres.session() as session:
            paid_orders, revenue = (
                await session.execute(
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

            sold_tickets = await session.scalar(
                select(func.count())
                .select_from(EventSeat)
                .where(
                    EventSeat.event_id == event_id,
                    EventSeat.status == SeatStatus.sold,
                )
            )

        return SalesDashboard(
            paid_orders=paid_orders,
            sold_tickets=sold_tickets or 0,
            revenue=revenue,
            average_order=revenue // paid_orders if paid_orders else 0,
        )

    async def _load_occupancy(self, event_id: int) -> OccupancyDashboard:
        now = datetime.now(UTC)
        reserved_active = and_(
            EventSeat.status == SeatStatus.reserved,
            EventSeat.reserved_until > now,
        )

        async with self._postgres.session() as session:
            total, reserved, sold = (
                await session.execute(
                    select(
                        func.count(),
                        func.count().filter(reserved_active),
                        func.count().filter(EventSeat.status == SeatStatus.sold),
                    )
                    .select_from(EventSeat)
                    .where(EventSeat.event_id == event_id)
                )
            ).one()

        occupancy_percent = round((reserved + sold) / total * 100, 2) if total else 0.0
        return OccupancyDashboard(
            total=total,
            available=total - reserved - sold,
            reserved=reserved,
            sold=sold,
            occupancy_percent=occupancy_percent,
        )
