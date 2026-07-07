"""Fetches a user from the DummyJSON API."""

import httpx
import json
from pydantic import ValidationError

from .exceptions import (
    DummyJsonError,
    DummyJsonUserNotFoundError,
    DummyJsonInvalidResponseError,
)
from .schemas import DummyJsonUserResponse


async def get_user(user_id: int, client: httpx.AsyncClient) -> DummyJsonUserResponse:
    """Fetches a user from the DummyJSON API."""

    try:
        response = await client.get(f"https://dummyjson.com/users/{user_id}")
        response.raise_for_status()
    except httpx.HTTPStatusError as error:
        if error.response.status_code == 404:
            raise DummyJsonUserNotFoundError(
                f"DummyJSON user {user_id} not found"
            ) from error

        raise DummyJsonError(
            f"DummyJSON returned HTTP {error.response.status_code}"
        ) from error
    except httpx.RequestError as error:
        raise DummyJsonError("Request to DummyJSON failed") from error

    try:
        payload = response.json()
    except json.JSONDecodeError as error:
        raise DummyJsonInvalidResponseError(
            "Invalid JSON received from DummyJSON"
        ) from error

    try:
        return DummyJsonUserResponse.model_validate(payload)
    except ValidationError as error:
        raise DummyJsonInvalidResponseError(
            "DummyJSON response validation failed"
        ) from error
