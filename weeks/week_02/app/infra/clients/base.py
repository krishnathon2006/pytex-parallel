import logging
from contextlib import nullcontext
from typing import Any

import httpx
from aiolimiter import AsyncLimiter
from tenacity import (
    AsyncRetrying,
    before_sleep_log,
    retry_if_exception,
    stop_after_attempt,
    wait_random_exponential,
)

logger = logging.getLogger(__name__)

RETRYABLE_STATUS_CODES = {429, 502, 503, 504}


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TransportError):
        return True
    return (
        isinstance(exc, httpx.HTTPStatusError)
        and exc.response.status_code in RETRYABLE_STATUS_CODES
    )


class BaseHTTPConnector:
    def __init__(
        self,
        base_url: str,
        timeout: float,
        headers: dict[str, str] | None = None,
        rate_limit_requests: int | None = None,
        rate_limit_interval: float = 1.0,
        retry_count: int = 4,
        retry_base_delay: float = 0.2,
        retry_max_delay: float = 2.0,
    ):
        self._client = httpx.AsyncClient(
            base_url=base_url, headers=headers, timeout=timeout
        )
        self._rate_limiter = (
            AsyncLimiter(rate_limit_requests, rate_limit_interval)
            if rate_limit_requests
            else None
        )
        self.retry_count = retry_count
        self._retry_base_delay = retry_base_delay
        self._retry_max_delay = retry_max_delay

    async def close_client(self) -> None:
        await self._client.aclose()

    async def _send(self, method: str, path: str, **kwargs) -> httpx.Response:
        async with self._rate_limiter if self._rate_limiter else nullcontext():
            response = await self._client.request(method, path, **kwargs)

        if response.status_code in RETRYABLE_STATUS_CODES:
            response.raise_for_status()
        return response

    async def _request(
        self, method: str, url: str, retry: bool = False, **kwargs: Any
    ) -> httpx.Response:
        if not retry:
            return await self._send(method, url, **kwargs)

        retryer = AsyncRetrying(
            retry=retry_if_exception(_is_retryable),
            stop=stop_after_attempt(self.retry_count),
            wait=wait_random_exponential(
                multiplier=self._retry_base_delay, max=self._retry_max_delay
            ),
            before_sleep=before_sleep_log(logger, logging.WARNING),
        )
        return await retryer(self._send, method, url, **kwargs)
