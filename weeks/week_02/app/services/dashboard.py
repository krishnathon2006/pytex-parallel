import asyncio
from datetime import UTC, datetime

from app.exceptions import AccessDeniedError, EventNotFoundError
from app.infra.postgres.postgres import PostgresClient
from app.infra.postgres.repositories.bookings import BookingRepository
from app.infra.postgres.repositories.event_seats import EventSeatRepository
from app.infra.postgres.repositories.events import EventRepository
from app.schemas import EventDashboard, OccupancyDashboard, SalesDashboard


class DashboardService:
    def __init__(self, postgres: PostgresClient) -> None:
        self._postgres = postgres

    async def get_event_dashboard(
        self, event_id: int, organizer_id: int
    ) -> EventDashboard:
        async with self._postgres.session() as session:
            event = await EventRepository(session).get(event_id)

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
            paid_orders, revenue = await BookingRepository(session).sales_totals(
                event_id
            )
            sold_tickets = await EventSeatRepository(session).count_sold(event_id)

        return SalesDashboard(
            paid_orders=paid_orders,
            sold_tickets=sold_tickets,
            revenue=revenue,
            average_order=revenue // paid_orders if paid_orders else 0,
        )

    async def _load_occupancy(self, event_id: int) -> OccupancyDashboard:
        now = datetime.now(UTC)

        async with self._postgres.session() as session:
            total, reserved, sold = await EventSeatRepository(session).occupancy_counts(
                event_id, now
            )

        occupancy_percent = round((reserved + sold) / total * 100, 2) if total else 0.0
        return OccupancyDashboard(
            total=total,
            available=total - reserved - sold,
            reserved=reserved,
            sold=sold,
            occupancy_percent=occupancy_percent,
        )
