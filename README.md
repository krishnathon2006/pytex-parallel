# Python Concurrency Homeworks

Домашние задания для курса «Параллелизм в Python».

## Week 1: FastAPI Background Reports

A FastAPI service that generates user reports in the background using
[DummyJSON](https://dummyjson.com).

### Features

- Starts report generation without waiting for completion.
- Tracks background jobs in application memory.
- Uses a shared `httpx.AsyncClient` for asynchronous requests.
- Runs the blocking legacy client through `asyncio.to_thread`.
- Keeps `/ping` responsive while reports are generated.
- Stores successful results and safe error messages.

### Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)

### Installation

```bash
git clone https://github.com/krishnathon2006/pytex-parallel.git
cd pytex-parallel
uv sync
```

### Running the application

```bash
uv run fastapi run --workers 1
```

Interactive API documentation is available at:

```text
http://127.0.0.1:8000/docs
```

The application must run with one worker because jobs are stored in
process-local memory.

### API

#### Health check

```http
GET /ping
```

Response:

```json
{
  "status": "ok"
}
```

#### Start report generation

```http
POST /reports/{user_id}
```

Example:

```bash
curl -X POST http://127.0.0.1:8000/reports/1
```

Response:

```json
{
  "job_id": "some-unique-id",
  "status": "running",
  "result": null,
  "error": null
}
```

#### Check report status

```http
GET /reports/jobs/{job_id}
```

Example:

```bash
curl http://127.0.0.1:8000/reports/jobs/<job_id>
```

Possible statuses:

- `running`
- `done`
- `error`

A completed job contains user information and todo statistics. A failed job
contains a safe error message.

### Concurrency design

`POST /reports/{user_id}` schedules report generation using
`asyncio.create_task` and returns immediately.

The report combines:

1. User data fetched asynchronously from DummyJSON.
2. Todo data fetched by the blocking legacy client.
3. A mapped API response containing user and todo statistics.

The legacy function runs with `asyncio.to_thread`, preventing it from blocking
FastAPI's event loop.

### Code quality checks

```bash
# Verify formatting without changing files.
uvx ruff format --check weeks

# Run linting and static analysis.
uvx ruff check weeks

# Check type annotations.
uv run --with mypy mypy weeks
```

### Limitations

- Jobs and results are stored only in memory.
- Jobs are lost when the application restarts.
- Multiple server workers do not share job state.
- The legacy client is intentionally unchanged and uses its own HTTP timeout.
- Report generation depends on the availability and latency of DummyJSON.
