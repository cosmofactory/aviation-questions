# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Domain Context

This is a **RAG (Retrieval-Augmented Generation) system for aviation law**. It answers questions about aviation regulations, manuals, and guidance material by retrieving relevant document chunks via vector similarity search and feeding them as context to an LLM.

### How the RAG Pipeline Works

```
Aviation documents (PDF/ODT/HTML)
    → Ingestion (parse, normalize, split into chunks)
    → Embedding (vectorize each chunk via an embedding model)
    → Storage (Postgres + pgvector: text, metadata, and embedding per chunk)
    → Retrieval (user question → embed → ANN search → top-k chunks)
    → Generation (LLM answers using retrieved chunks as context, with citations)
```

### Domain Concepts

- **Documents**: Aviation-law sources — EU regulations (e.g. Reg 965/2012), ICAO annexes, FAA advisory circulars, airline operations manuals, AIPs. Each document version is a separate row with `effective_from`/`effective_to` for "in force" logic.
- **Jurisdictions**: EASA, FAA, ICAO, or national authorities. Documents are classified by jurisdiction and type (regulation, implementing rule, manual, guidance, AIP, circular).
- **Chunks**: Documents are split into text chunks with structural metadata — `section_path` (e.g. "Part-ORO > Subpart FC > ORO.FC.105"), `citation` (e.g. "ORO.FC.105(a)"), and `heading`. Each chunk has a 1536-dim embedding vector for cosine similarity search via pgvector HNSW index.
- **Ingestion runs**: ETL audit trail tracking each document import (status, timing, error diagnostics, chunk statistics).
- **Deduplication**: SHA-256 checksums on both documents and chunks prevent re-ingesting or re-embedding identical content.

### Feature Modules

| Module | Bounded context | Status |
| --- | --- | --- |
| `src/documents/` | Document storage, chunking, embeddings, ingestion tracking | Models defined |

### Postgres Extensions Required

```sql
CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- gen_random_uuid() for UUID PKs
CREATE EXTENSION IF NOT EXISTS "vector";      -- pgvector: Vector column type + HNSW/IVFFlat indexes
```

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

## Architecture Overview

**Modular monolith with DDD (Domain-Driven Design)** built on FastAPI + SQLAlchemy async, using `uv` for dependency management. Python 3.13+.

### Database

Local PostgreSQL with **pgvector** and **pgcrypto** extensions. Vector similarity search via HNSW index with cosine distance. Embedding dimension is configured in `src/documents/constants.py` (`EMBEDDING_DIM = 1536`). SQLAlchemy integration via the `pgvector` Python package — use `Vector(EMBEDDING_DIM)` column type.

Each business domain lives in its own feature module under `src/`. Modules are self-contained and communicate through explicit interfaces — never by importing each other's internals.

## Project Structure

```
src/
├── main.py                          # FastAPI app entry point, lifespan, middleware
├── settings.py                      # Global settings (DB, auth, external services)
├── core/                            # Shared infrastructure — NOT business logic
│   ├── engine.py                    # Database class, Base declarative model
│   ├── sessions.py                  # ReadDBSession / WriteDBSession dependencies
│   ├── base_dao.py                  # Generic BaseDAO with CRUD + bulk ops
│   ├── models.py                    # TimeStampedModel mixin
│   ├── schema.py                    # OrmModel, PaginatedResponse base schemas
│   ├── dependencies.py              # Shared deps (HttpxDep, PaginationParams)
│   ├── exceptions.py                # Base HTTP exceptions
│   └── http_mixin.py                # BaseHTTPMixin for external API clients
├── <feature>/                       # One folder per bounded context
│   ├── __init__.py
│   ├── router.py                    # FastAPI router — HTTP layer only
│   ├── service.py                   # Business logic / use cases
│   ├── dao.py                       # Data access — BaseDAO subclass
│   ├── models.py                    # SQLAlchemy ORM models for this domain
│   ├── schemas.py                   # Pydantic request/response schemas
│   ├── dependencies.py              # Feature-specific FastAPI dependencies
│   ├── exceptions.py                # Domain-specific exceptions
│   ├── enums.py                     # Feature-specific enums (StrEnum subclasses)
│   └── constants.py                 # Feature-specific constants
├── migrations/                      # Alembic migrations (shared across all modules)
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
└── utils/                           # Pure utility functions (no business logic)
    ├── constants.py
    └── enums.py

tests/
├── conftest.py                      # Global fixtures (DB, async client)
├── <feature>/
│   ├── conftest.py                  # Feature-specific fixtures and factories
│   ├── test_router.py               # Endpoint integration tests
│   ├── test_service.py              # Service unit tests
│   └── test_dao.py                  # DAO tests (if complex queries exist)
```

## DDD Module Rules

These rules keep modules decoupled. Follow them strictly when adding or modifying features.

### 1. Feature module boundaries

Each feature folder is a **bounded context**. It owns its models, schemas, business logic, and routes.

- A feature module **MUST** contain at minimum: `router.py`, `service.py`, `dao.py`, `models.py`, `schemas.py`.
- Additional files (`dependencies.py`, `exceptions.py`, `constants.py`) are added only when needed.
- The feature router is registered in `src/main.py` with a URL prefix matching the feature name (e.g., `app.include_router(questions.router, prefix="/questions", tags=["Questions"])`).

### 2. Dependency direction (strict layering)

```
router.py  →  service.py  →  dao.py  →  models.py
    ↓              ↓
schemas.py    dependencies.py
```

- **router.py**: Thin HTTP layer. Handles request/response, calls service methods. No business logic, no direct DB access.
- **service.py**: All business logic and use cases. Receives a DB session (or other deps) via arguments. Returns domain objects or schemas. Calls DAO methods for persistence.
- **dao.py**: Data access only. Subclasses `BaseDAO`, sets `model = YourModel`. Add custom query methods here. No business logic.
- **models.py**: SQLAlchemy ORM models. Inherit from `TimeStampedModel` (provides UUID PK + timestamps). Define relationships, constraints, indexes.
- **schemas.py**: Pydantic models for API input/output. Inherit from `OrmModel` or `STimetampedModel`.

**Never skip layers**: routers must not call DAOs directly. Services must not construct HTTP responses.

### 3. Cross-module communication

The **only** public interface of a feature module is its `service.py`. When feature A needs data from feature B, A's service imports and calls B's **service** — nothing else.

- **Allowed**: `from src.documents.service import DocumentService`
- **Forbidden**: Importing another module's DAO, models, schemas, enums, constants, or dependencies. If two domains need a shared concept, extract it into `core/`.

```python
# GOOD — src/search/service.py
from src.documents.service import DocumentService

# BAD — never import internals from another module
from src.documents.dao import DocumentDAO          # forbidden
from src.documents.models import Document          # forbidden
from src.documents.schemas import DocumentResponse # forbidden
```

### 4. What goes in `core/` vs a feature module

| Belongs in `core/`                            | Belongs in a feature module          |
| --------------------------------------------- | ------------------------------------ |
| Database engine, session management           | Domain models and relationships      |
| BaseDAO, base schemas, base exceptions        | Domain-specific schemas              |
| Generic middleware, auth dependencies         | Feature-specific dependencies        |
| HTTP client base class                        | External API integration services    |
| Shared utilities with zero domain knowledge   | Business rules and validation logic  |

**Rule of thumb**: If it mentions a business concept (question, user, exam), it belongs in a feature module.

## Core Infrastructure Reference

### Database (`src/core/engine.py`)

`Database` class wraps async SQLAlchemy engine. Two session types:
- `get_read_only_session()` — auto-rollback, for queries
- `get_write_session()` — auto-commit on success, auto-rollback on error

The `Database` instance lives on `app.state.postgres_db`, initialized in the lifespan handler.

### Session Dependencies (`src/core/sessions.py`)

- `ReadDBSession` — annotated dependency for read-only endpoints
- `WriteDBSession` — annotated dependency for write endpoints

Use as endpoint parameters: `async def get_items(session: ReadDBSession):`

### BaseDAO (`src/core/base_dao.py`)

Generic CRUD + bulk operations. Subclass and set `model`:

```python
class QuestionDAO(BaseDAO):
    model = Question
```

Available classmethods: `get_all`, `get_first`, `get_one_or_none`, `get_by_id`, `get_paginated`, `get_object_or_error`, `create`, `update`, `delete`, `bulk_create`, `bulk_update`, `bulk_delete`, `bulk_get`.

### Models

Inherit from `TimeStampedModel` (`src/core/models.py`) which provides `id` (UUID v4 PK via `gen_random_uuid()`), `created_at`, and `updated_at`. All feature models should use `TimeStampedModel` as their base class instead of `Base` directly.

### Schemas

- `OrmModel` — base Pydantic model with `from_attributes=True`
- `STimetampedModel` — adds `created_at`/`updated_at` fields
- `PaginatedResponse` — generic wrapper for paginated results
- `ErrorResponse` — standard error shape

### Settings (`src/settings.py`)

Pydantic Settings with env prefix pattern (`DB_`, `AUTH_`, `S3_`, `EMAIL_`). Loaded from `.env`.

### External HTTP Clients

Subclass `BaseHTTPMixin` (`src/core/http_mixin.py`) for third-party API integrations. Provides Bearer auth, URL building, logging, and convenience methods (`get_json`, `post_json`).

### Admin

SQLAdmin integration initialized in the lifespan. Admin views go in `src/admin/`.

### Observability

Logfire integration (`logfire.instrument_fastapi`, `logfire.instrument_sqlalchemy`, `logfire.instrument_httpx`).

## Creating a New Feature Module

Step-by-step guide for adding a new bounded context:

1. **Create the feature directory**: `src/<feature_name>/` with `__init__.py`.
2. **Define models** in `models.py` — inherit `TimeStampedModel`.
3. **Define schemas** in `schemas.py` — inherit `OrmModel`.
4. **Create DAO** in `dao.py` — subclass `BaseDAO`, set `model`.
5. **Implement service** in `service.py` — business logic, receives session as arg.
6. **Create router** in `router.py` — define endpoints, inject deps, call service.
7. **Register router** in `src/main.py`: `app.include_router(...)`.
8. **Generate migration**: `make makemigrations` then `make migrate`.
9. **Add tests** in `tests/<feature_name>/` — router, service, and DAO tests.
10. **Run checks**: `make lint && make type && make test`.

### Example: Minimal Feature Module

```python
# src/questions/models.py
from sqlalchemy.orm import Mapped, mapped_column

from src.core.models import TimeStampedModel

class Question(TimeStampedModel):
    __tablename__ = "questions"
    text: Mapped[str]
    answer: Mapped[str]
```

```python
# src/questions/schemas.py
import uuid
from src.core.schema import OrmModel, STimetampedModel

class QuestionCreate(OrmModel):
    text: str
    answer: str

class QuestionResponse(STimetampedModel):
    id: uuid.UUID
    text: str
    answer: str
```

```python
# src/questions/dao.py
from src.core.base_dao import BaseDAO
from src.questions.models import Question

class QuestionDAO(BaseDAO):
    model = Question
```

```python
# src/questions/service.py
from sqlalchemy.ext.asyncio import AsyncSession
from src.questions.dao import QuestionDAO
from src.questions.schemas import QuestionCreate

class QuestionService:
    @staticmethod
    async def create_question(session: AsyncSession, data: QuestionCreate) -> Question:
        return await QuestionDAO.create(session=session, values=data.model_dump())

    @staticmethod
    async def get_all_questions(session: AsyncSession):
        return await QuestionDAO.get_all(session=session)
```

```python
# src/questions/router.py
from fastapi import APIRouter
from src.core.sessions import ReadDBSession, WriteDBSession
from src.questions.schemas import QuestionCreate, QuestionResponse
from src.questions.service import QuestionService

router = APIRouter()

@router.post("/", response_model=QuestionResponse)
async def create_question(session: WriteDBSession, data: QuestionCreate):
    return await QuestionService.create_question(session, data)

@router.get("/", response_model=list[QuestionResponse])
async def list_questions(session: ReadDBSession):
    return await QuestionService.get_all_questions(session)
```

## Testing

### Structure

Tests mirror the feature structure: `tests/<feature>/test_router.py`, `test_service.py`, etc.

### Test Database

Tests use a **PostgreSQL test database** (same credentials as main DB, `_test` suffix on DB name) via dependency overrides in `tests/conftest.py`. Tables are created once per session and dropped after. The `session` fixture provides a transactional session that rolls back after each test; `ac` gives an `AsyncClient` with DB overrides. pytest-asyncio in auto mode (`asyncio_mode = "auto"`).

### Test Conventions

- Use factories or fixtures in `tests/<feature>/conftest.py` to create domain objects.
- Router tests use the `ac` (AsyncClient) fixture and assert HTTP status + response shape.
- Service tests use the `session` fixture directly.
- Mock external services; never make real HTTP calls in tests.

## Linting

Ruff with 100-char line length. Extends with `I` (isort), `W` (warnings), `B` (bugbear). Migrations excluded from linting.

## Type Checking

Uses `ty` (Astral's type checker). If a typing issue comes from a third-party library or is too complex to fix cleanly (e.g., Starlette/Pydantic internals), add the rule as an exception in `[tool.ty.rules]` in `pyproject.toml` rather than scattering `# type: ignore` comments.

## Development Workflow

After implementing a code change:

1. Add or update tests if the change warrants it.
2. Run `make lint` — fix any formatting or lint errors.
3. Run `make type` — fix any type errors.
4. Run `make test` — ensure all tests pass.

## Common Mistakes to Avoid

- **Putting business logic in routers** — routers are thin; logic goes in services.
- **Calling DAOs from routers** — always go through a service.
- **Importing another feature's models directly** — go through its service or DAO.
- **Adding domain concepts to `core/`** — core is infrastructure only.
- **Creating cross-module SQLAlchemy relationships** — keep model ownership within one module.
- **Skipping migrations after model changes** — always run `make makemigrations`.
- **Writing tests without rollback** — use the `session` fixture for automatic cleanup.
