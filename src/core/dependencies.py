from collections.abc import AsyncGenerator
from typing import Annotated

import httpx
from fastapi import Depends, Request
from fastapi_pagination.limit_offset import LimitOffsetParams

from src.core.s3 import S3Client


async def get_http_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient() as client:
        yield client


HttpxDep = Annotated[httpx.AsyncClient, Depends(get_http_client)]


PaginationParams = Annotated[
    LimitOffsetParams,
    Depends(LimitOffsetParams),
]


async def get_s3_client(request: Request) -> S3Client:
    return request.app.state.s3


S3ClientDep = Annotated[S3Client, Depends(get_s3_client)]
