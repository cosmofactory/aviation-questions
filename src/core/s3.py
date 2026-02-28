"""
Async S3 client for uploading and downloading documents.

Uses aiobotocore for non-blocking S3 operations. Compatible with AWS S3
and S3-compatible services (MinIO, DigitalOcean Spaces, etc.) via
``S3_ENDPOINT_URL``.

Usage:
    s3 = S3Client(settings.s3)

    # In the lifespan handler:
    async with s3:
        app.state.s3 = s3
        yield

    # In a service:
    await s3.upload(key="docs/reg-965.pdf", data=file_bytes, content_type="application/pdf")
    data = await s3.download(key="docs/reg-965.pdf")
    url = await s3.generate_presigned_url(key="docs/reg-965.pdf")
    await s3.delete(key="docs/reg-965.pdf")
"""

from __future__ import annotations

from types import TracebackType
from typing import Any

from aiobotocore.session import AioSession
from botocore.exceptions import ClientError

from src.settings import S3Settings


class S3Client:
    """Async S3 client wrapping an aiobotocore session."""

    def __init__(self, settings: S3Settings) -> None:
        self._settings = settings
        self._session = AioSession()
        self._client_ctx: Any = None
        self._client: Any = None

    async def __aenter__(self) -> S3Client:
        self._client_ctx = self._session.create_client(
            "s3",
            endpoint_url=self._settings.ENDPOINT_URL or None,
            region_name=self._settings.REGION,
            aws_access_key_id=self._settings.ACCESS_KEY_ID,
            aws_secret_access_key=self._settings.SECRET_ACCESS_KEY,
        )
        self._client = await self._client_ctx.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self._client_ctx:
            await self._client_ctx.__aexit__(exc_type, exc_val, exc_tb)
        self._client = None
        self._client_ctx = None

    @property
    def _bucket(self) -> str:
        return self._settings.BUCKET_NAME

    async def upload(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> None:
        """Upload bytes to S3."""
        await self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )

    async def download(self, key: str) -> bytes:
        """Download an object from S3 and return its bytes."""
        response = await self._client.get_object(Bucket=self._bucket, Key=key)
        async with response["Body"] as stream:
            return await stream.read()

    async def delete(self, key: str) -> None:
        """Delete an object from S3."""
        await self._client.delete_object(Bucket=self._bucket, Key=key)

    async def generate_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        """Generate a presigned URL for temporary access to an object."""
        return await self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expires_in,
        )

    async def exists(self, key: str) -> bool:
        """Check if an object exists in S3."""
        try:
            await self._client.head_object(Bucket=self._bucket, Key=key)
            return True
        except ClientError:
            return False
