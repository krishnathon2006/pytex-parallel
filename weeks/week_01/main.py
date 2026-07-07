import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

import httpx
from fastapi import FastAPI
from .health import router as health_router
from .reports.router import router as reports_router

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s  %(levelname)s %(name)s: %(message)s"
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    log = logging.getLogger("lifespan")
    log.info("Application started")
    async with httpx.AsyncClient(
        base_url="https://dummyjson.com", timeout=10.0
    ) as client:
        app.state.dummyjson_client = client
        yield

    log.info("Application stopped")


app = FastAPI(lifespan=lifespan)

app.include_router(health_router)
app.include_router(reports_router)
