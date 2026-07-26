import asyncio
import logging
from datetime import datetime

import httpx

from app.config import PROTECTION_API_URL
from app.infra.clients.base import BaseHTTPConnector
from app.schemas import ProtectionQuote

logger = logging.getLogger(__name__)

QUOTE_BUDGET_SECONDS = 3.0


class ProtectionClient(BaseHTTPConnector):
    def __init__(self) -> None:
        super().__init__(base_url=PROTECTION_API_URL, timeout=10.0)

    async def calculate(
        self,
        booking_id: int,
        ticket_amount: int,
        event_category: str,
        event_starts_at: datetime,
    ) -> ProtectionQuote | None:
        payload = {
            "booking_id": booking_id,
            "ticket_amount": ticket_amount,
            "event_category": event_category,
            "event_starts_at": event_starts_at.isoformat(),
        }
        try:
            async with asyncio.timeout(QUOTE_BUDGET_SECONDS):
                response = await self._request(
                    "POST", "/protection/calculate", json=payload
                )
                response.raise_for_status()
                return ProtectionQuote.model_validate(response.json())
        except (
            TimeoutError,
            httpx.TransportError,
            httpx.HTTPStatusError,
            ValueError,
        ) as exc:
            logger.warning(
                "Protection quote unavailable for booking %s: %r", booking_id, exc
            )
            return None
