from typing import Annotated

from fastapi import Depends, Request

from app.db import postgres
from app.services.checkout import CheckoutService
from app.services.dashboard import DashboardService
from app.services.events import EventService


def get_event_service() -> EventService:
    return EventService(postgres)


EventServiceDep = Annotated[EventService, Depends(get_event_service)]


def get_checkout_service(request: Request) -> CheckoutService:
    return CheckoutService(
        postgres, request.app.state.payment_client, request.app.state.protection_client
    )


CheckoutServiceDep = Annotated[CheckoutService, Depends(get_checkout_service)]


def get_dashboard_service() -> DashboardService:
    return DashboardService(postgres)


DashboardServiceDep = Annotated[DashboardService, Depends(get_dashboard_service)]
