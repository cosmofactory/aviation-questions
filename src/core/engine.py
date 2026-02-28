from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncAttrs, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from src.settings import settings


class Database:
    """
    Holds the async engine and session factory for your application.

    Usage:
        db = Database(database_url="postgresql+asyncpg://...")
        async with db.get_read_only_session() as session:
            # do read-only work
        async with db.get_write_session() as session:
            # do read/write work
        await db.dispose()
    """

    def __init__(
        self,
        database_url: str = settings.database.DATABASE_URL,
        echo: bool = False,
        pool_size: int = settings.database.POOL_SIZE,
        max_overflow: int = settings.database.MAX_OVERFLOW,
        pool_recycle: int = settings.database.POOL_RECYCLE,
        pool_pre_ping: bool = settings.database.POOL_PRE_PING,
        pool_reset_on_return: str | None = settings.database.POOL_RESET_ON_RETURN,
    ):
        """
        Create a Database instance.

        Args:
            database_url: Async DB URL, e.g. "postgresql+asyncpg://user:pass@host/db".
            echo: If True, SQLAlchemy will log all SQL statements.

        Example:
            db = Database(database_url="postgresql+asyncpg://...", echo=True)
        """
        self._engine = create_async_engine(
            database_url,
            echo=echo,
            future=True,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_recycle=pool_recycle,
            pool_pre_ping=pool_pre_ping,
            pool_reset_on_return=pool_reset_on_return,
        )
        self._session_factory = async_sessionmaker(
            self._engine,
            expire_on_commit=False,
        )

    @asynccontextmanager
    async def get_read_only_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Yield an AsyncSession for read-only operations.

        Rolls back any accidental writes before closing.

        Yields:
            AsyncSession: session configured for reads only.

        Example:
            async with db.get_read_only_session() as session:
                result = await session.execute(select(User))
                users = result.scalars().all()
        """
        async with self._session_factory() as session:
            try:
                yield session
            finally:
                await session.rollback()

    @asynccontextmanager
    async def get_write_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Yield an AsyncSession wrapped in a transaction.

        Commits on success and rolls back on exception.

        Yields:
            AsyncSession: session inside a BEGIN/COMMIT block.

        Example:
            async with db.get_write_session() as session:
                user = User(name="Alice")
                session.add(user)
        """
        async with self._session_factory() as session:
            try:
                async with session.begin():
                    yield session
            except Exception:
                await session.rollback()
                raise

    @property
    def sessionmaker(self) -> async_sessionmaker[AsyncSession]:
        """
        Get the sessionmaker for creating new AsyncSession instances.

        Returns:
            async_sessionmaker[AsyncSession]: The sessionmaker for creating new AsyncSession instances.
        """
        return self._session_factory

    async def dispose(self) -> None:
        """
        Dispose of the async engine and its connection pool.

        Call this when your application is shutting down to release resources.

        Example:
            await db.dispose()
        """
        await self._engine.dispose()


class Base(AsyncAttrs, DeclarativeBase):
    """
    Base class for ORM models.

    AsyncAttrs is needed to use attributes of the model that are part of another model.
    If you get MissingGreenlet exception while working with ORM models, add this:
        trip.locations - MissingGreenlet exception
        trip.awaitable_attrs.locations - works fine
    Wanna know more?
    https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html#preventing-implicit-io-when-using-asyncsession
    """

    pass
