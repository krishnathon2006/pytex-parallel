from sqlalchemy import select

from app.infra.postgres.repositories.base import BaseRepository
from app.models import Seat


class SeatRepository(BaseRepository):
    async def map_by_ids(self, seat_ids: list[int]) -> dict[int, Seat]:
        result = await self._session.scalars(select(Seat).where(Seat.id.in_(seat_ids)))

        return {seat.id: seat for seat in result}
