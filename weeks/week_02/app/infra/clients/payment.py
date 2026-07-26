import httpx
from tenacity import RetryError

from app.config import PAYMENT_API_URL
from app.exceptions import PaymentUnavailableError
from app.infra.clients.base import BaseHTTPConnector
from app.schemas import PaymentQuote


class PaymentClient(BaseHTTPConnector):
    def __init__(self) -> None:
        super().__init__(
            base_url=PAYMENT_API_URL,
            timeout=2.0,
            rate_limit_requests=5,
            rate_limit_interval=1.0,
            retry_count=4,
        )

    async def calculate(self, booking_id: int, amount: int) -> PaymentQuote:
        payload = {"booking_id": booking_id, "amount": amount, "currency": "RUB"}
        try:
            response = await self._request(
                "POST", "/payment/calculate", retry=True, json=payload
            )
            response.raise_for_status()
            return PaymentQuote.model_validate(response.json())
        except RetryError as exc:
            raise PaymentUnavailableError(
                f"Payment API failed after {self.retry_count} attempts"
            ) from exc
        except (httpx.HTTPStatusError, ValueError) as exc:
            # ValueError covers json.JSONDecodeError and pydantic.ValidationError.
            raise PaymentUnavailableError(
                f"Payment API returned an unexpected response: {exc}"
            ) from exc
