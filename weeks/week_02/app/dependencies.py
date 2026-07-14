from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session, postgres
from app.services.checkout import CheckoutService
from app.services.dashboard import DashboardService
from app.services.events import EventService

DatabaseSession = Annotated[AsyncSession, Depends(get_session)]


def get_event_service(session: DatabaseSession) -> EventService:
    return EventService(session)


EventServiceDep = Annotated[EventService, Depends(get_event_service)]


def get_checkout_service(request: Request) -> CheckoutService:
    return CheckoutService(
        postgres, request.app.state.payment_client, request.app.state.protection_client
    )


CheckoutServiceDep = Annotated[CheckoutService, Depends(get_checkout_service)]


def get_dashboard_service() -> DashboardService:
    return DashboardService(postgres)


DashboardServiceDep = Annotated[DashboardService, Depends(get_dashboard_service)]
