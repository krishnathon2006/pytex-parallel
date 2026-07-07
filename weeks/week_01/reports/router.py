from typing import Annotated

import httpx
from fastapi import APIRouter, Depends

from . import service
from .schemas import JobResponse
from ..dummyjson.dependencies import get_dummyjson_client

router = APIRouter()


@router.post("/reports/{user_id}", response_model=JobResponse, tags=["reports"])
async def schedule_report_generation(
    user_id: int, client: Annotated[httpx.AsyncClient, Depends(get_dummyjson_client)]
) -> JobResponse:
    return await service.start_report(user_id, client)


@router.get("/reports/jobs/{job_id}", response_model=JobResponse, tags=["reports"])
async def get_report(job_id: str) -> JobResponse:
    return await service.get_job(job_id)
