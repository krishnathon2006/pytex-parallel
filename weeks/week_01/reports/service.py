import asyncio
import logging
import time
from uuid import uuid4

import httpx
from fastapi import HTTPException, status
from pydantic import ValidationError

from . import mappers
from .entities import JobStatus
from .schemas import JobResponse
from ..dummyjson import client as dummy_json_client
from ..dummyjson import legacy_client as sync_dummyjson_client
from ..dummyjson.exceptions import DummyJsonError, DummyJsonUserNotFoundError
from ..dummyjson.schemas import DummyJsonUserTodoResponse

jobs: dict[str, JobResponse] = {}
background_tasks: dict[str, asyncio.Task[None]] = {}

log = logging.getLogger(__name__)


def _mark_job_as_failed(job_id: str, error_message: str) -> None:
    job = jobs[job_id]
    job.status = JobStatus.ERROR
    job.error = error_message


async def _build_report(job_id: str, user_id: int, client: httpx.AsyncClient) -> None:
    started_at = time.perf_counter()
    log.info(
        "Report generation started with id %s for user with id %d", job_id, user_id
    )
    try:
        async with asyncio.TaskGroup() as tg:
            user_task = tg.create_task(dummy_json_client.get_user(user_id, client))
            todo_task = tg.create_task(
                asyncio.to_thread(sync_dummyjson_client.get_user_todos_sync, user_id)
            )

        user_payload, raw_todos = user_task.result(), todo_task.result()

        user = mappers.to_user(user_payload)
        todos_response = DummyJsonUserTodoResponse.model_validate(raw_todos)
        todos = mappers.to_todos(todos_response)

        result = mappers.to_result(user, todos)

        job = jobs[job_id]
        job.status = JobStatus.DONE
        job.result = result
    except* DummyJsonUserNotFoundError:
        message = f"User with id {user_id} not found"
        log.warning(message)
        _mark_job_as_failed(job_id, message)
    except* (DummyJsonError, httpx.RequestError, ValidationError):
        message = f"Error building report for user with id {user_id}"
        log.exception(message)
        _mark_job_as_failed(job_id, message)
    except* Exception:
        message = f"Unexpected error building report for user with id {user_id}"

        log.exception(message)
        _mark_job_as_failed(job_id, message)
    finally:
        background_tasks.pop(job_id, None)
        log.info(
            "Report generation finished with id %s for user with id %d in %.2f seconds",
            job_id,
            user_id,
            time.perf_counter() - started_at,
        )


async def start_report(user_id: int, client: httpx.AsyncClient) -> JobResponse:
    """Starts generating a report for a user."""
    job_id = str(uuid4())
    log.info(
        "Starting generating report with id %s for user with id %d", job_id, user_id
    )
    job = JobResponse(job_id=job_id, status=JobStatus.RUNNING)
    jobs[job_id] = job

    task = asyncio.create_task(_build_report(job_id, user_id, client))
    background_tasks[job_id] = task

    return job


async def get_job(job_id: str) -> JobResponse:
    """Gets a scheduled background job by id."""
    log.info("Getting job with id %s", job_id)
    if job_id not in jobs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with id {job_id} not found",
        )

    return jobs[job_id]
