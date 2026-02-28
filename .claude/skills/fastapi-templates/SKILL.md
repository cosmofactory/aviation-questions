---
name: fastapi-templates
description: Create production-ready FastAPI feature modules following DDD modular monolith architecture. Use when adding new features, endpoints, or bounded contexts.
---

# FastAPI DDD Modular Monolith Templates

Templates for building feature modules in a DDD modular monolith architecture with FastAPI, async SQLAlchemy, and strict layering.

## When to Use This Skill

- Adding a new feature module (bounded context)
- Creating new endpoints within an existing feature
- Setting up service, DAO, models, schemas for a domain
- Scaffolding tests for a feature module

## Architecture: Modular Monolith with DDD

Each business domain is a self-contained feature module under `src/`. Shared infrastructure lives in `src/core/`.

### Project Structure

```
src/
├── main.py                          # App entry point, lifespan, router registration
├── settings.py                      # Global settings (Pydantic Settings)
├── core/                            # Shared infrastructure (NO business logic)
│   ├── engine.py                    # Database class, Base model
│   ├── sessions.py                  # ReadDBSession / WriteDBSession
│   ├── base_dao.py                  # Generic BaseDAO (CRUD + bulk)
│   ├── models.py                    # TimeStampedModel mixin
│   ├── schema.py                    # OrmModel, PaginatedResponse
│   ├── dependencies.py              # HttpxDep, PaginationParams
│   ├── exceptions.py                # Base HTTP exceptions
│   └── http_mixin.py                # BaseHTTPMixin for external APIs
├── <feature>/                       # Bounded context
│   ├── __init__.py
│   ├── router.py                    # FastAPI router (HTTP layer only)
│   ├── service.py                   # Business logic / use cases
│   ├── dao.py                       # Data access (BaseDAO subclass)
│   ├── models.py                    # SQLAlchemy ORM models
│   ├── schemas.py                   # Pydantic request/response schemas
│   ├── dependencies.py              # Feature-specific dependencies (optional)
│   ├── exceptions.py                # Domain-specific exceptions (optional)
│   └── constants.py                 # Feature constants/enums (optional)
├── migrations/                      # Alembic (shared)
└── utils/                           # Pure utilities (no domain logic)

tests/
├── conftest.py                      # Global fixtures
├── <feature>/
│   ├── conftest.py                  # Feature fixtures and factories
│   ├── test_router.py               # Endpoint integration tests
│   ├── test_service.py              # Service unit tests
│   └── test_dao.py                  # DAO tests (if needed)
```

### Dependency Direction (Strict Layering)

```
router.py  →  service.py  →  dao.py  →  models.py
    ↓              ↓
schemas.py    dependencies.py
```

- **router** calls **service** (never DAO directly)
- **service** calls **DAO** (contains all business logic)
- **DAO** handles persistence (no business logic)

## Complete Feature Module Template

### 1. Models (`src/<feature>/models.py`)

```python
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.engine import Base
from src.core.models import TimeStampedModel


class Question(Base, TimeStampedModel):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    text: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(100))
    difficulty: Mapped[int] = mapped_column(default=1)

    answers: Mapped[list["Answer"]] = relationship(back_populates="question", lazy="selectin")


class Answer(Base, TimeStampedModel):
    __tablename__ = "answers"

    id: Mapped[int] = mapped_column(primary_key=True)
    text: Mapped[str] = mapped_column(Text)
    is_correct: Mapped[bool] = mapped_column(default=False)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"))

    question: Mapped["Question"] = relationship(back_populates="answers")
```

### 2. Schemas (`src/<feature>/schemas.py`)

```python
from src.core.schema import OrmModel, STimetampedModel


class QuestionCreate(OrmModel):
    text: str
    category: str
    difficulty: int = 1


class QuestionUpdate(OrmModel):
    text: str | None = None
    category: str | None = None
    difficulty: int | None = None


class QuestionResponse(STimetampedModel):
    id: int
    text: str
    category: str
    difficulty: int


class QuestionDetailResponse(QuestionResponse):
    answers: list["AnswerResponse"]


class AnswerCreate(OrmModel):
    text: str
    is_correct: bool = False


class AnswerResponse(STimetampedModel):
    id: int
    text: str
    is_correct: bool
    question_id: int
```

### 3. DAO (`src/<feature>/dao.py`)

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.base_dao import BaseDAO
from src.questions.models import Answer, Question


class QuestionDAO(BaseDAO):
    model = Question

    @classmethod
    async def get_with_answers(cls, session: AsyncSession, question_id: int) -> Question | None:
        query = (
            select(Question)
            .options(selectinload(Question.answers))
            .where(Question.id == question_id)
        )
        result = await session.execute(query)
        return result.scalar_one_or_none()

    @classmethod
    async def get_by_category(cls, session: AsyncSession, category: str) -> list[Question]:
        query = select(Question).where(Question.category == category)
        result = await session.execute(query)
        return list(result.scalars().all())


class AnswerDAO(BaseDAO):
    model = Answer
```

### 4. Service (`src/<feature>/service.py`)

```python
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import ObjectNotFoundException
from src.questions.dao import AnswerDAO, QuestionDAO
from src.questions.models import Question
from src.questions.schemas import AnswerCreate, QuestionCreate, QuestionUpdate


class QuestionService:
    @staticmethod
    async def create_question(session: AsyncSession, data: QuestionCreate) -> Question:
        return await QuestionDAO.create(session=session, values=data.model_dump())

    @staticmethod
    async def get_question(session: AsyncSession, question_id: int) -> Question:
        question = await QuestionDAO.get_with_answers(session, question_id)
        if not question:
            raise ObjectNotFoundException(detail="Question not found")
        return question

    @staticmethod
    async def list_questions(session: AsyncSession) -> list[Question]:
        return await QuestionDAO.get_all(session=session)

    @staticmethod
    async def update_question(
        session: AsyncSession, question_id: int, data: QuestionUpdate
    ) -> Question:
        return await QuestionDAO.update(
            session=session,
            instance=await QuestionDAO.get_object_or_error(session, question_id),
            values=data.model_dump(exclude_unset=True),
        )

    @staticmethod
    async def delete_question(session: AsyncSession, question_id: int) -> None:
        await QuestionDAO.delete(session=session, instance_id=question_id)

    @staticmethod
    async def add_answer(
        session: AsyncSession, question_id: int, data: AnswerCreate
    ) -> None:
        await QuestionDAO.get_object_or_error(session, question_id)
        await AnswerDAO.create(
            session=session, values={**data.model_dump(), "question_id": question_id}
        )
```

### 5. Router (`src/<feature>/router.py`)

```python
from fastapi import APIRouter

from src.core.sessions import ReadDBSession, WriteDBSession
from src.questions.schemas import (
    AnswerCreate,
    QuestionCreate,
    QuestionDetailResponse,
    QuestionResponse,
    QuestionUpdate,
)
from src.questions.service import QuestionService

router = APIRouter()


@router.post("/", response_model=QuestionResponse, status_code=201)
async def create_question(session: WriteDBSession, data: QuestionCreate):
    return await QuestionService.create_question(session, data)


@router.get("/", response_model=list[QuestionResponse])
async def list_questions(session: ReadDBSession):
    return await QuestionService.list_questions(session)


@router.get("/{question_id}", response_model=QuestionDetailResponse)
async def get_question(session: ReadDBSession, question_id: int):
    return await QuestionService.get_question(session, question_id)


@router.patch("/{question_id}", response_model=QuestionResponse)
async def update_question(session: WriteDBSession, question_id: int, data: QuestionUpdate):
    return await QuestionService.update_question(session, question_id, data)


@router.delete("/{question_id}", status_code=204)
async def delete_question(session: WriteDBSession, question_id: int):
    await QuestionService.delete_question(session, question_id)


@router.post("/{question_id}/answers", status_code=201)
async def add_answer(session: WriteDBSession, question_id: int, data: AnswerCreate):
    await QuestionService.add_answer(session, question_id, data)
```

### 6. Register Router (`src/main.py`)

```python
from src.questions.router import router as questions_router

app.include_router(questions_router, prefix="/questions", tags=["Questions"])
```

## Database Infrastructure

### Database Class (`src/core/engine.py`)

```python
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncAttrs, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


class Database:
    def __init__(self, database_url: str, **pool_kwargs):
        self._engine = create_async_engine(database_url, **pool_kwargs)
        self._session_factory = async_sessionmaker(self._engine, expire_on_commit=False)

    @asynccontextmanager
    async def get_read_only_session(self) -> AsyncGenerator[AsyncSession, None]:
        async with self._session_factory() as session:
            try:
                yield session
            finally:
                await session.rollback()

    @asynccontextmanager
    async def get_write_session(self) -> AsyncGenerator[AsyncSession, None]:
        async with self._session_factory() as session:
            try:
                async with session.begin():
                    yield session
            except Exception:
                await session.rollback()
                raise

    async def dispose(self) -> None:
        await self._engine.dispose()


class Base(AsyncAttrs, DeclarativeBase):
    pass
```

### Session Dependencies (`src/core/sessions.py`)

```python
from typing import Annotated
from collections.abc import AsyncGenerator
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession


async def get_read_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    async with request.app.state.postgres_db.get_read_only_session() as session:
        yield session

async def get_write_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    async with request.app.state.postgres_db.get_write_session() as session:
        yield session

ReadDBSession = Annotated[AsyncSession, Depends(get_read_session)]
WriteDBSession = Annotated[AsyncSession, Depends(get_write_session)]
```

## Testing Templates

### Global Fixtures (`tests/conftest.py`)

```python
import asyncio
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core.engine import Base
from src.core.sessions import get_read_session, get_write_session
from src.settings import settings

TEST_DATABASE_URL = f"{settings.db.url}_test"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
test_session_factory = async_sessionmaker(test_engine, expire_on_commit=False)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
async def setup_database():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest.fixture
async def session() -> AsyncGenerator[AsyncSession, None]:
    async with test_session_factory() as session:
        async with session.begin():
            yield session
            await session.rollback()


@pytest.fixture
async def ac(session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    from src.main import app

    async def override_read():
        yield session

    async def override_write():
        yield session

    app.dependency_overrides[get_read_session] = override_read
    app.dependency_overrides[get_write_session] = override_write

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client

    app.dependency_overrides.clear()
```

### Feature Test (`tests/<feature>/test_router.py`)

```python
import pytest
from httpx import AsyncClient


async def test_create_question(ac: AsyncClient):
    response = await ac.post(
        "/questions/",
        json={"text": "What is V1?", "category": "takeoff", "difficulty": 1},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["text"] == "What is V1?"
    assert "id" in data


async def test_list_questions(ac: AsyncClient):
    response = await ac.get("/questions/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


async def test_get_question_not_found(ac: AsyncClient):
    response = await ac.get("/questions/99999")
    assert response.status_code == 404
```

### Feature Service Test (`tests/<feature>/test_service.py`)

```python
from sqlalchemy.ext.asyncio import AsyncSession

from src.questions.schemas import QuestionCreate
from src.questions.service import QuestionService


async def test_create_and_get_question(session: AsyncSession):
    data = QuestionCreate(text="What is V1?", category="takeoff", difficulty=1)
    question = await QuestionService.create_question(session, data)

    assert question.id is not None
    assert question.text == "What is V1?"

    fetched = await QuestionService.get_question(session, question.id)
    assert fetched.id == question.id
```

## Cross-Module Communication

When feature A needs data from feature B:

```python
# src/exams/service.py
from src.questions.service import QuestionService  # Import the SERVICE, not DAO/models


class ExamService:
    @staticmethod
    async def generate_exam(session: AsyncSession, category: str, count: int):
        questions = await QuestionService.list_by_category(session, category)
        # ... exam generation logic using questions
```

**Rules:**
- Import another module's **service** (preferred) or **DAO** (acceptable for reads)
- Never import another module's **models** into your DAO
- Never create cross-module SQLAlchemy relationships

## Best Practices

1. **Thin routers**: HTTP concerns only — no business logic
2. **Fat services**: All domain logic lives here
3. **Explicit dependencies**: Pass session/deps as arguments, don't use globals
4. **One DAO per model**: Keep data access focused
5. **Schema separation**: Separate Create, Update, and Response schemas
6. **Feature isolation**: Each module owns its models, schemas, and logic
7. **Test all layers**: Router (integration), service (unit), DAO (if complex)

## Common Pitfalls

- **Business logic in routers**: Move it to the service layer
- **Calling DAO from router**: Always go through a service
- **Cross-module model imports**: Use services for cross-module data access
- **Domain concepts in core/**: Core is infrastructure only
- **Skipping migrations**: Always run `make makemigrations` after model changes
- **Missing `__init__.py`**: Every feature folder needs one
