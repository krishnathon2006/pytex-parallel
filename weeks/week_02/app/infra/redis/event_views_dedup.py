from redis.asyncio import Redis

from app import config


class EventViewsDedupe:
    """Отсекает повторные просмотры мероприятия с одного IP."""

    def __init__(self, redis: Redis) -> None:
        self._redis = redis
        self._cache_prefix = "view:event:v1:"

    async def mark_viewed(self, event_id: int, ip: str) -> bool:
        """True, если это первый просмотр за окно дедупликации.

        SET NX не трогает TTL уже существующего ключа, поэтому окно
        фиксированное — отсчитывается от первого просмотра, а не сдвигается.
        """
        prev_value = await self._redis.set(
            f"{self._cache_prefix}{event_id}:{ip}",
            value="1",
            ex=config.REDIS_EVENT_VIEW_DEDUPE_TTL_SECONDS,
            nx=True,
        )

        return bool(prev_value)
