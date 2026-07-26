from typing import Annotated

from fastapi import APIRouter, Depends, Header

from app.dependencies import CheckoutServiceDep, DashboardServiceDep, EventServiceDep
from app.schemas import (
    BookingCreate,
    CheckoutBooking,
    CheckoutResponse,
    EventCreate,
    EventDashboard,
    EventRead,
    EventSeatRead,
    LocationDetail,
    LocationRead,
    PaymentCompleted,
    PaymentCreate,
    SeatRead,
)

router = APIRouter()


def get_current_user_id(x_user_id: Annotated[int, Header()]) -> int:
    return x_user_id


CurrentUserId = Annotated[int, Depends(get_current_user_id)]


@router.get("/locations", tags=["locations"])
async def list_locations() -> list[LocationRead]:
    """Возвращает список площадок."""
    ...


@router.get("/locations/{location_id}", tags=["locations"])
async def get_location(location_id: int) -> LocationDetail:
    """Возвращает площадку со схемой мест."""
    ...


@router.get("/locations/{location_id}/seats", tags=["locations"])
async def list_location_seats(location_id: int) -> list[SeatRead]:
    """Возвращает все места площадки."""
    ...


@router.get("/events", tags=["events"])
async def list_events(service: EventServiceDep) -> list[EventRead]:
    """Возвращает список мероприятий для клиента."""
    events = await service.list_events()
    return [EventRead.model_validate(event) for event in events]


@router.get("/events/{event_id}", tags=["events"])
async def get_event(event_id: int) -> EventRead:
    """Возвращает описание мероприятия."""
    ...


@router.get("/events/{event_id}/seats", tags=["events"])
async def list_event_seats(event_id: int) -> list[EventSeatRead]:
    """Возвращает места на мероприятии с ценами и статусами."""
    ...


@router.get("/organizer/events", tags=["organizer"])
async def list_organizer_events(organizer_id: CurrentUserId) -> list[EventRead]:
    """Возвращает список созданных событий текущего организатора."""
    ...


@router.post("/organizer/events", tags=["organizer"])
async def create_event(payload: EventCreate, organizer_id: CurrentUserId) -> EventRead:
    """Создает мероприятие от лица текущего организатора."""
    ...


@router.get("/organizer/events/{event_id}/dashboard", tags=["organizer"])
async def get_event_dashboard(
    event_id: int,
    organizer_id: CurrentUserId,
    dashboard_service: DashboardServiceDep,
) -> EventDashboard:
    """Возвращает аналитические данные для дашборда по мероприятию."""
    return await dashboard_service.get_event_dashboard(event_id, organizer_id)


@router.post("/events/{event_id}/checkout", tags=["events"])
async def prepare_checkout(
    event_id: int,
    payload: BookingCreate,
    user_id: CurrentUserId,
    checkout_service: CheckoutServiceDep,
) -> CheckoutResponse:
    """Временно бронирует места за клиентом, возвращает итоговую стоимость
    и возможность страховки."""
    result = await checkout_service.prepare_checkout(
        event_id, payload.seat_ids, user_id
    )
    booking = result.booking
    protection = result.protection
    checkout_booking = CheckoutBooking(
        id=booking.id,
        event_title=result.event.title,
        starts_at=result.event.starts_at,
        seats=result.seats,
        base_amount=booking.amount,
        payment_commission=result.payment.commission,
        protection_price=protection.price
        if protection and protection.available
        else None,
        with_protection=booking.with_protection,
        reserved_until=booking.reserved_until,
    )
    return CheckoutResponse(
        booking=checkout_booking, payment=result.payment, protection=protection
    )


@router.post("/bookings/{booking_id}/pay", tags=["bookings"])
async def pay_booking(
    booking_id: int,
    payload: PaymentCreate,
    user_id: CurrentUserId,
) -> PaymentCompleted:
    """Принимает способ оплаты и флаг with_protection."""
    ...
