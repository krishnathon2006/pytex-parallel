from typing import Annotated

from fastapi import Depends, Request
from redis.asyncio import Redis

from app.db import postgres
from app.infra.clients.payment import PaymentClient
from app.infra.clients.protection import ProtectionClient
from app.infra.redis.event_cache import EventCache
from app.infra.redis.event_views_dedup import EventViewsDedupe
from app.services.checkout import CheckoutService
from app.services.dashboard import DashboardService
from app.services.event_views import EventViewsConsolidator, EventViewsService
from app.services.events import EventService

# starlette отдает app.state как Any, поэтому все, что из него достается,
# аннотируется явно — иначе ошибки связывания не видит ни mypy, ни IDE.


def get_event_service(request: Request) -> EventService:
    redis: Redis = request.app.state.redis
    return EventService(postgres, EventCache(redis))


EventServiceDep = Annotated[EventService, Depends(get_event_service)]


def get_event_views_service(request: Request) -> EventViewsService:
    redis: Redis = request.app.state.redis
    consolidator: EventViewsConsolidator = request.app.state.view_consolidator
    return EventViewsService(EventViewsDedupe(redis), consolidator)


EventViewsServiceDep = Annotated[EventViewsService, Depends(get_event_views_service)]


def get_checkout_service(request: Request) -> CheckoutService:
    payment_client: PaymentClient = request.app.state.payment_client
    protection_client: ProtectionClient = request.app.state.protection_client
    return CheckoutService(postgres, payment_client, protection_client)


CheckoutServiceDep = Annotated[CheckoutService, Depends(get_checkout_service)]


def get_dashboard_service() -> DashboardService:
    return DashboardService(postgres)


DashboardServiceDep = Annotated[DashboardService, Depends(get_dashboard_service)]
