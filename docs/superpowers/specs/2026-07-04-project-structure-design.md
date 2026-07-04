# pytex Project Structure — Weekly FastAPI Homeworks

**Date:** 2026-07-04
**Status:** Approved

## Context

pytex is a personal learning repo for a FastAPI course. Each week brings a new
homework. Homeworks are mostly independent; some may later build on earlier
weeks (undecided). There are no external constraints on layout or run command.

The current layout (`weeks/week_01/src/`) made the import root ambiguous.
Three conflicting import styles coexist in week 1, two of them broken:

- `main.py` uses relative imports — works.
- `dummyjson/client.py` and `reports/schemas.py` use `from src....` — there is
  no top-level `src` package when running from the repo root, so they fail.
- `reports/router.py` line 8 uses `import ..dummyjson.client as ...` — a
  `SyntaxError` (relative imports require the `from ... import` form). The app
  cannot start.

## Decision

**One uv project; one flat package per week; relative imports within a week.**

Alternatives considered and rejected:

- *uv workspace (a pyproject per week):* clean isolation but per-week
  boilerplate and a packaging learning curve on top of FastAPI. Revisit only
  if a week ever needs conflicting dependencies.
- *Single app mounting weeks as routers:* one broken work-in-progress week
  would crash all finished weeks, and non-API homeworks would not fit.

## Structure

```
pytex/
├── pyproject.toml          # single project; [tool.fastapi] entrypoint → current week
├── uv.lock
├── README.md               # how to run any week, how to run tests
├── docs/superpowers/specs/ # design docs
└── weeks/
    ├── __init__.py
    ├── week_01/
    │   ├── __init__.py
    │   ├── main.py         # app = FastAPI(); includes routers
    │   ├── health.py
    │   ├── dummyjson/
    │   │   ├── __init__.py
    │   │   ├── client.py
    │   │   ├── legacy_client.py
    │   │   └── schemas.py
    │   ├── reports/
    │   │   ├── __init__.py
    │   │   ├── entities.py
    │   │   ├── router.py
    │   │   ├── schemas.py
    │   │   └── service.py
    │   └── tests/
    │       ├── __init__.py
    │       └── test_health.py
    └── week_02/            # future weeks copy this shape
```

The `src/` layer is removed. Week naming stays `week_NN` (zero-padded,
underscore).

## Rules

1. **Imports of a week's own modules are always relative.** Same package:
   `from .schemas import UserResponse`. Sibling package:
   `from ..dummyjson import client`. Never `from src....` and never
   `from weeks.week_NN....` inside week code. This keeps each week
   self-contained and copyable. The only absolute import permitted in week
   code is the shared package from Rule 2.
2. **No cross-week imports.** If sharing is ever needed, add a
   `weeks/common/` package and import it as `from weeks.common import ...`
   (decided when it happens, not before).
3. **Every package directory has an `__init__.py`** so FastAPI CLI can detect
   the package structure from the repo root.
4. **`[tool.fastapi] entrypoint` always points at the current week**, e.g.
   `weeks.week_01.main:app`. `uv run fastapi dev` therefore always runs the
   current homework. Older weeks stay runnable explicitly:
   `uv run fastapi dev weeks/week_01/main.py`.
5. **Starting a new week:** create `weeks/week_NN/` with `__init__.py`,
   `main.py`, `tests/`; update the entrypoint line; add a line to the README.

## Testing

- `pytest` added as a dev dependency group (`uv add --dev pytest`).
- Each week has its own `tests/` package.
- Week 1 is seeded with one example test: `GET /ping` returns
  `200 {"status": "ok"}`, using `fastapi.testclient.TestClient`.
- Run with `uv run pytest`.

## Migration Steps (week_01)

1. Move everything from `weeks/week_01/src/` up one level into
   `weeks/week_01/`; delete the `src/` directory and its `__init__.py`.
2. Fix the broken imports — four lines across three files:
   - `dummyjson/client.py`: `from src.dummyjson.schemas import UserResponse`
     → `from .schemas import UserResponse`
   - `reports/schemas.py`: `from src.reports.entities import JobStatus`
     → `from .entities import JobStatus`
   - `reports/router.py`: delete `import dummyjson` and replace
     `import ..dummyjson.client as dummy_json_client` with
     `from ..dummyjson import client as dummy_json_client`
3. Update `pyproject.toml` entrypoint to `weeks.week_01.main:app`.
4. Add the pytest dev group and `weeks/week_01/tests/test_health.py`.
5. Rewrite the root README: project purpose, run current week, run a specific
   week, run tests.

All other homework code is preserved byte-for-byte.

## Verification

- `uv run python -m compileall -q weeks` exits 0.
- `uv run fastapi dev` starts; `GET /ping` returns `200 {"status": "ok"}`.
- `uv run pytest` passes.
- `git diff` shows no homework-logic changes beyond the import fixes above.

## Out of Scope

Known logic bugs in week 1 homework code, left for the author to fix as part
of learning:

- `reports/router.py`: `User.model_validate(user.model_dump_json())` passes a
  JSON string where a dict is expected, and `User`'s field names
  (`user_id`, `user_name`) do not match `UserResponse`'s (`id`, `first_name`,
  …).
- `reports/router.py`: code after the `return` in
  `schedule_report_generation` is unreachable and references an undefined
  `job_id`.
- `reports/schemas.py`: `TodoItem` does not inherit `BaseModel`.
- `reports/service.py` is empty.

Also out of scope until a homework needs them: database, settings management,
Docker, CI.
