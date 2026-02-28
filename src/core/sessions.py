from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession


async def get_read_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """Get a PostgreSQL read session."""
    async with request.app.state.postgres_db.get_read_only_session() as session:
        yield session


ReadDBSession = Annotated[AsyncSession, Depends(get_read_session)]


async def get_write_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """Get a PostgreSQL write session."""
    async with request.app.state.postgres_db.get_write_session() as session:
        yield session


WriteDBSession = Annotated[AsyncSession, Depends(get_write_session)]
