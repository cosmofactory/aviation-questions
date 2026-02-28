# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Development
make run                    # Run FastAPI dev server (uv run fastapi dev src/main.py)
make run_container          # Run in Docker (docker compose up --build)
make test                   # Run tests (uv run pytest)
make lint                   # Format + lint (ruff format, ruff check --fix, ruff check)
make type                   # Type checking with ty (uv run ty)

# Single test
uv run pytest tests/test_file.py::test_name -vv

# Migrations (Alembic)
make makemigrations         # Create migration (alembic revision --autogenerate)
make migrate                # Apply migrations (alembic upgrade head)
make revert_migration       # Revert last migration (alembic downgrade -1)
```

## Architecture

**FastAPI + SQLAlchemy async service** using `uv` for dependency management. Python 3.13+.

### Core Patterns

- **Database (`src/core/engine.py`)**: `Database` class wraps async SQLAlchemy engine. Two session types: `get_read_only_session()` (auto-rollback) and `get_write_session()` (auto-commit/rollback). The `Database` instance lives on `app.state.postgres_db` and is initialized in the lifespan handler.

- **Session dependencies (`src/core/sessions.py`)**: FastAPI dependencies `ReadDBSession` and `WriteDBSession` pull the `Database` from `request.app.state` and yield the appropriate session type. Use these as endpoint parameters.

- **DAO pattern (`src/core/base_dao.py`)**: `BaseDAO` provides generic CRUD + bulk operations. Subclass it, set `model = YourModel`, and use classmethods like `get_all`, `get_by_id`, `create`, `update`, `delete`, `bulk_create`, etc.

- **Models**: Inherit from `Base` (in `engine.py`). Use `TimeStampedModel` (`src/core/models.py`) for `created_at`/`updated_at` columns.

- **Schemas**: Inherit from `OrmModel` (`src/core/schema.py`, sets `from_attributes=True`) or `STimetampedModel` for timestamped responses.

- **Settings (`src/settings.py`)**: Pydantic Settings with env prefix pattern (e.g., `DB_`, `AUTH_`, `S3_`, `EMAIL_`). Loaded from `.env` file.

- **External HTTP clients**: Subclass `BaseHTTPMixin` (`src/core/http_mixin.py`) for third-party API integrations. Provides Bearer auth, URL building, logging, and convenience methods (`get_json`, `post_json`).

- **Admin**: SQLAdmin integration initialized in the lifespan. Admin views go in `src/admin/`.

- **Observability**: Logfire integration (`logfire.instrument_fastapi`).

### Testing

Tests use a **PostgreSQL test database** (same credentials as main DB, with `_test` suffix on DB name) via dependency overrides in `tests/conftest.py`. Tables are created once per session and dropped after. The `session` fixture provides a transactional session that rolls back after each test; `ac` gives an `AsyncClient` with DB overrides. pytest-asyncio in auto mode (`asyncio_mode = "auto"`). Requires the test database to exist (e.g., `createdb <DB_NAME>_test`).

### Linting

Ruff with 100-char line length. Extends with `I` (isort), `W` (warnings), `B` (bugbear). Migrations excluded from linting.

### Type Checking

Uses `ty` (Astral's type checker). If a typing issue comes from a third-party library or is too complex to fix cleanly (e.g., Starlette/Pydantic internals), add the rule as an exception in `[tool.ty.rules]` in `pyproject.toml` rather than scattering `# type: ignore` comments.

### Development Workflow

After implementing a code change:

1. Add or update tests if the change warrants it.
2. Run `make lint` — fix any formatting or lint errors.
3. Run `make type` — fix any type errors.
4. Run `make test` — ensure all tests pass.
