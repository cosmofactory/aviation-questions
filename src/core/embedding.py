"""
Async embedding client backed by pydantic-ai.

Uses `pydantic_ai.Embedder` + `OpenAIEmbeddingModel` so embeddings follow the
same library stack as the QA agent.
"""

from __future__ import annotations

from types import TracebackType

from pydantic_ai.embeddings import Embedder
from pydantic_ai.embeddings.openai import OpenAIEmbeddingModel
from pydantic_ai.models.instrumented import InstrumentationSettings
from pydantic_ai.providers.openai import OpenAIProvider

from src.settings import OpenAISettings


class EmbeddingClient:
    """Thin adapter around pydantic-ai's embedding APIs."""

    def __init__(self, settings: OpenAISettings) -> None:
        self._model = settings.EMBEDDING_MODEL
        self._provider = OpenAIProvider(api_key=settings.API_KEY)
        model = OpenAIEmbeddingModel(self._model, provider=self._provider)
        instrument = _build_instrumentation_settings(settings)
        self._embedder = Embedder(
            model,
            settings={"dimensions": settings.EMBEDDING_DIMENSIONS},
            defer_model_check=True,
            instrument=instrument,
        )

    async def __aenter__(self) -> EmbeddingClient:
        # Kept for compatibility with app lifespan initialization.
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self._provider.client.close()

    async def embed_text(self, text: str) -> list[float]:
        """Embed a single query string, returning a float vector."""
        result = await self._embedder.embed_query(text)
        return list(result.embeddings[0])

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed document texts, returning vectors in input order."""
        if not texts:
            return []

        result = await self._embedder.embed_documents(texts)
        return [list(embedding) for embedding in result.embeddings]


def _build_instrumentation_settings(
    settings: OpenAISettings,
) -> InstrumentationSettings | bool:
    if not settings.EMBEDDING_INSTRUMENT:
        return False

    return InstrumentationSettings(
        include_content=settings.EMBEDDING_INSTRUMENT_INCLUDE_CONTENT,
        include_binary_content=settings.EMBEDDING_INSTRUMENT_INCLUDE_BINARY_CONTENT,
        version=2,
    )
