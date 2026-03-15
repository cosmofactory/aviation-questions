import asyncio
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import Enum as SAEnum
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core.dependencies import get_embedding_client, get_s3_client
from src.core.engine import Base
from src.core.sessions import get_read_session, get_write_session
from src.documents import models as _documents_models  # noqa: F401 — register models with Base
from src.questions import models as _questions_models  # noqa: F401 — register models with Base
from src.settings import settings

# Build the test database URL from settings, appending "_test" to the DB name
TEST_DATABASE_URL = (
    f"postgresql+asyncpg://{settings.database.USER}:{settings.database.PASSWORD}"
    f"@{settings.database.HOST}:{settings.database.PORT}/{settings.database.NAME}_test"
)

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
db_session_factory = async_sessionmaker(test_engine, expire_on_commit=False)


@pytest.fixture(scope="session")
def event_loop():
    """Create a single event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
async def setup_database():
    """Create all tables before tests and drop them after.

    Enum types are created in a separate connection first because asyncpg
    caches type OIDs — if an enum is created and referenced as a column
    default in the same connection, asyncpg fails to resolve the value.
    """
    # 1. Create enum types in their own connection
    async with test_engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            for col in table.columns:
                if isinstance(col.type, SAEnum):
                    await conn.run_sync(
                        lambda sync_conn, t=col.type: t.create(sync_conn, checkfirst=True)
                    )

    # 2. Dispose pool so step 3 gets a fresh connection without stale type cache
    await test_engine.dispose()

    # 3. Create tables in a fresh connection (asyncpg now sees the enum types)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest.fixture
async def session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional session that rolls back after each test."""
    async with db_session_factory() as session:
        async with session.begin():
            yield session
            await session.rollback()


@pytest.fixture
def mock_s3() -> AsyncMock:
    """Provide a mock S3Client with async no-op methods."""
    s3 = AsyncMock()
    s3.upload = AsyncMock()
    s3.delete = AsyncMock()
    s3.exists = AsyncMock(return_value=False)
    s3._bucket = "test-bucket"
    return s3


@pytest.fixture
def mock_embedding_client() -> AsyncMock:
    """Provide a mock EmbeddingClient that returns zero vectors."""
    client = AsyncMock()
    client._model = "text-embedding-3-small"
    client.embed_text = AsyncMock(return_value=[0.0] * 1536)
    client.embed_texts = AsyncMock(side_effect=lambda texts: [[0.0] * 1536 for _ in texts])
    return client


@pytest.fixture
async def ac(
    mock_s3: AsyncMock, mock_embedding_client: AsyncMock
) -> AsyncGenerator[AsyncClient, None]:
    """Provide an AsyncClient with test DB session and mock S3 overrides.

    Uses independent sessions from the test engine (not the shared transactional
    session) to avoid event-loop conflicts between the test and ASGI transport.
    """
    from src.main import app

    async def override_read_session():
        async with db_session_factory() as s:
            yield s

    async def override_write_session():
        async with db_session_factory() as s:
            async with s.begin():
                yield s

    app.dependency_overrides[get_read_session] = override_read_session
    app.dependency_overrides[get_write_session] = override_write_session
    app.dependency_overrides[get_s3_client] = lambda: mock_s3
    app.dependency_overrides[get_embedding_client] = lambda: mock_embedding_client

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client

    app.dependency_overrides.clear()
