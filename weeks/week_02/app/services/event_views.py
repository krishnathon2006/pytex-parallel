import asyncio
import logging
from collections import defaultdict
from contextlib import suppress

from app import config
from app.infra.postgres.postgres import PostgresClient
from app.infra.postgres.repositories.event_views import EventViewsRepository
from app.infra.redis.event_views_dedup import EventViewsDedupe

logger = logging.getLogger(__name__)


class EventViewsConsolidator:
    """Копит просмотры в памяти и пишет их в Postgres пачками."""

    def __init__(self, postgres: PostgresClient) -> None:
        self._postgres = postgres
        self._queue: asyncio.Queue[int | None] = asyncio.Queue(
            maxsize=config.VIEWS_QUEUE_MAXSIZE
        )
        self._batch: defaultdict[int, int] = defaultdict(int)
        self._pending = 0
        self._task: asyncio.Task[None] | None = None

    def submit(self, event_id: int) -> None:
        """Ставит просмотр в очередь. Синхронный и неблокирующий: счетчик
        просмотров не должен задерживать ответ пользователю."""
        try:
            self._queue.put_nowait(event_id)
        except asyncio.QueueFull:
            logger.warning("Views queue is full, dropping view for event %s", event_id)

    async def start(self) -> None:
        """Поднимает фоновый воркер. Вызывается из lifespan."""
        self._task = asyncio.create_task(self._run())
        logger.info("Views worker started")

    async def stop(self) -> None:
        """Досыпает остаток в БД и останавливает воркер.

        Обязана отработать до закрытия postgres, иначе финальный сброс
        накопленных просмотров писать уже некуда.
        """
        if self._task is None:
            return
        try:
            async with asyncio.timeout(config.VIEWS_SHUTDOWN_TIMEOUT_SECONDS):
                # None — сигнал воркеру: дослить остаток и выйти.
                await self._queue.put(None)
                await self._task
        except TimeoutError:
            logger.error(
                "Views worker did not finish in time, losing %s views", self._pending
            )
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
        finally:
            self._task = None

    async def _run(self) -> None:
        deadline = self._next_deadline()
        while True:
            try:
                async with asyncio.timeout_at(deadline):
                    event_id = await self._queue.get()
            except TimeoutError:
                await self._flush()
                deadline = self._next_deadline()
                continue

            if event_id is None:
                await self._flush()
                return

            self._batch[event_id] += 1
            self._pending += 1

            if self._pending >= config.VIEWS_FLUSH_BATCH_SIZE:
                await self._flush()
                deadline = self._next_deadline()

    @staticmethod
    def _next_deadline() -> float:
        return asyncio.get_running_loop().time() + config.VIEWS_FLUSH_INTERVAL_SECONDS

    async def _flush(self) -> None:
        if not self._batch:
            return
        try:
            async with self._postgres.transaction() as session:
                await EventViewsRepository(session).add_views(self._batch)
        except Exception:
            # Батч не сбрасываем — попробуем записать его следующей пачкой.
            logger.exception("Failed to flush %s views, keeping them", self._pending)
            return

        logger.info("Flushed %s views for %s events", self._pending, len(self._batch))
        self._batch.clear()
        self._pending = 0


class EventViewsService:
    """Учитывает просмотр мероприятия: дедупликация по IP плюс постановка
    в очередь на агрегацию."""

    def __init__(
        self, dedupe: EventViewsDedupe, consolidator: EventViewsConsolidator
    ) -> None:
        self._dedupe = dedupe
        self._consolidator = consolidator

    async def record(self, event_id: int, ip: str) -> None:
        """Учитывает просмотр, если он уникален.

        Ошибки глушатся намеренно: счетчик просмотров не должен ронять
        запрос, по которому мероприятие уже успешно отдано.
        """
        try:
            if await self._dedupe.mark_viewed(event_id, ip):
                self._consolidator.submit(event_id)
        except Exception:
            logger.exception("Failed to record view for event %s", event_id)
