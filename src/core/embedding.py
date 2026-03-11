"""
Async OpenAI embedding client.

Uses httpx for non-blocking calls to the OpenAI embeddings API.
Logfire auto-instruments httpx, so all requests are traced.

Usage:
    client = EmbeddingClient(settings.openai)

    async with client:
        vec = await client.embed_text("What is ORO.FC.105?")
        vecs = await client.embed_texts(["text1", "text2"])
"""

from __future__ import annotations

from types import TracebackType

import httpx

from src.settings import OpenAISettings

OPENAI_EMBEDDINGS_URL = "https://api.openai.com/v1/embeddings"


class EmbeddingClient:
    """Async wrapper around the OpenAI embeddings endpoint."""

    def __init__(self, settings: OpenAISettings) -> None:
        self._model = settings.EMBEDDING_MODEL
        self._headers = {
            "Authorization": f"Bearer {settings.API_KEY}",
            "Content-Type": "application/json",
        }
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> EmbeddingClient:
        self._client = httpx.AsyncClient(headers=self._headers, timeout=30.0)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self._client:
            await self._client.aclose()
        self._client = None

    async def embed_text(self, text: str) -> list[float]:
        """Embed a single text string, returning a float vector."""
        result = await self.embed_texts([text])
        return result[0]

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts in a single API call, returning vectors in input order."""
        assert self._client is not None, "EmbeddingClient must be used as a context manager"

        response = await self._client.post(
            OPENAI_EMBEDDINGS_URL,
            json={"input": texts, "model": self._model},
        )
        response.raise_for_status()

        data = response.json()["data"]
        # API returns objects with index + embedding; sort by index to preserve order
        data.sort(key=lambda d: d["index"])
        return [d["embedding"] for d in data]
