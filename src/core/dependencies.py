from collections.abc import AsyncGenerator
from typing import Annotated

import httpx
from fastapi import Depends
from fastapi_pagination.limit_offset import LimitOffsetParams


async def get_http_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient() as client:
        yield client


HttpxDep = Annotated[httpx.AsyncClient, Depends(get_http_client)]


PaginationParams = Annotated[
    LimitOffsetParams,
    Depends(LimitOffsetParams),
]
