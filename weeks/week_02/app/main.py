from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis
from starlette.responses import JSONResponse

from app import config
from app.add_event_data import add_event_data_to_db
from app.db import postgres
from app.exceptions import (
    AccessDeniedError,
    DuplicateSeatError,
    EventNotFoundError,
    EventUnavailableError,
    PaymentUnavailableError,
    SeatsNotFoundError,
    SeatsUnavailableError,
)
from app.infra.clients.payment import PaymentClient
from app.infra.clients.protection import ProtectionClient
from app.routes import router
from app.services.event_views import EventViewsConsolidator


@asynccontextmanager
async def lifespan(app: FastAPI):
    await add_event_data_to_db()
    app.state.redis = Redis.from_url(config.REDIS_URL, decode_responses=True)
    await app.state.redis.ping()
    payment_client = PaymentClient()
    protection_client = ProtectionClient()
    app.state.payment_client = payment_client
    app.state.protection_client = protection_client
    app.state.view_consolidator = EventViewsConsolidator(postgres)
    await app.state.view_consolidator.start()

    try:
        yield
    finally:
        await app.state.view_consolidator.stop()
        await payment_client.close_client()
        await protection_client.close_client()
        await postgres.close()
        await app.state.redis.aclose()


ERROR_RESPONSES: dict[type[Exception], tuple[int, str]] = {
    EventNotFoundError: (status.HTTP_404_NOT_FOUND, "Event not found"),
    SeatsNotFoundError: (status.HTTP_404_NOT_FOUND, "Seats not found"),
    SeatsUnavailableError: (status.HTTP_409_CONFLICT, "Seats are unavailable"),
    DuplicateSeatError: (
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        "Seat ids must be unique",
    ),
    PaymentUnavailableError: (
        status.HTTP_502_BAD_GATEWAY,
        "Payment service is unavailable",
    ),
    AccessDeniedError: (status.HTTP_403_FORBIDDEN, "Access denied"),
    EventUnavailableError: (
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "Event is temporarily unavailable",
    ),
}


async def domain_error_handler(request: Request, exc: Exception) -> JSONResponse:
    for exc_class, (status_code, detail) in ERROR_RESPONSES.items():
        if isinstance(exc, exc_class):
            return JSONResponse(
                status_code=status_code, content={"detail": str(exc) or detail}
            )
    raise exc


app = FastAPI(title="API Афиши", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

for exc_class in ERROR_RESPONSES:
    app.add_exception_handler(exc_class, domain_error_handler)
