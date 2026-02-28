import asyncio
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core.engine import Base
from src.core.sessions import get_read_session, get_write_session
from src.settings import settings

# Build the test database URL from settings, appending "_test" to the DB name
TEST_DATABASE_URL = (
    f"postgresql+asyncpg://{settings.database.USER}:{settings.database.PASSWORD}"
    f"@{settings.database.HOST}:{settings.database.PORT}/{settings.database.NAME}_test"
)

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
test_session_factory = async_sessionmaker(test_engine, expire_on_commit=False)


@pytest.fixture(scope="session")
def event_loop():
    """Create a single event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
async def setup_database():
    """Create all tables before tests and drop them after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest.fixture
async def session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional session that rolls back after each test."""
    async with test_session_factory() as session:
        async with session.begin():
            yield session
            await session.rollback()


@pytest.fixture
async def ac(session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Provide an unauthenticated AsyncClient with DB session overrides."""
    from src.main import app

    async def override_read_session():
        yield session

    async def override_write_session():
        yield session

    app.dependency_overrides[get_read_session] = override_read_session
    app.dependency_overrides[get_write_session] = override_write_session

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client

    app.dependency_overrides.clear()
