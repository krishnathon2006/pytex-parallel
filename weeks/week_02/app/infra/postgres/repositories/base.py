from sqlalchemy.ext.asyncio import AsyncSession


class BaseRepository:
    """Работает внутри сессии, открытой вызывающим сервисом: границы транзакции
    остаются на стороне сервиса."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
