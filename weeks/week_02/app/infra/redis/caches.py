import random
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager, suppress

from redis.asyncio import Redis
from redis.exceptions import LockNotOwnedError

from app import config
from app.exceptions import EventUnavailableError
from app.schemas import EventRead


class EventCache:
    _NOT_FOUND_IN_DB = "null"

    def __init__(self, redis: Redis):
        self._redis = redis
        self._cache_prefix = "event:v1:"
        self._cache_lock_prefix = "lock:event:v1:"

    async def get_or_load(
        self, event_id: int, load_func: Callable[[], Awaitable[EventRead | None]]
    ) -> EventRead | None:
        found, value_from_cache = await self._get_cached(event_id)
        if found:
            return value_from_cache

        async with self._try_lock(event_id) as acquired:
            if not acquired:
                raise EventUnavailableError

            found, value_from_cache = await self._get_cached(event_id)
            if found:
                return value_from_cache

            value_from_db: EventRead | None = await load_func()

            await self._set(event_id, value_from_db)

            return value_from_db

    async def _get_cached(self, event_id: int) -> tuple[bool, EventRead | None]:
        value = await self._redis.get(self._get_cache_key(event_id))
        if value is None:
            return False, None
        if value == self._NOT_FOUND_IN_DB:
            return True, None
        return True, EventRead.model_validate_json(value)

    async def _set(self, event_id: int, value: EventRead | None) -> None:
        if value is None:
            payload = self._NOT_FOUND_IN_DB
            ttl = self._ttl_with_jitter(config.REDIS_EVENT_NOT_FOUND_TTL_SECONDS)
        else:
            payload = value.model_dump_json()
            ttl = self._ttl_with_jitter(config.REDIS_EVENT_CACHE_TTL_SECONDS)

        await self._redis.set(
            name=self._get_cache_key(event_id),
            value=payload,
            ex=ttl,
        )

    @staticmethod
    def _ttl_with_jitter(base_ttl: int) -> int:
        return base_ttl + random.randint(
            0, int(base_ttl * config.REDIS_EVENT_CACHE_TTL_JITTER_RATIO)
        )

    @asynccontextmanager
    async def _try_lock(self, event_id: int) -> AsyncIterator[bool]:
        lock = self._redis.lock(
            name=self._get_lock_key(event_id),
            timeout=config.REDIS_EVENT_LOCK_TTL_SECONDS,
            sleep=0.01,
        )
        acquired = await lock.acquire(
            blocking=True, blocking_timeout=config.REDIS_EVENT_LOCK_WAIT_SECONDS
        )
        try:
            yield acquired
        finally:
            if acquired:
                with suppress(LockNotOwnedError):
                    await lock.release()

    def _get_cache_key(self, event_id: int) -> str:
        return f"{self._cache_prefix}{event_id}"

    def _get_lock_key(self, event_id: int) -> str:
        return f"{self._cache_lock_prefix}{event_id}"
