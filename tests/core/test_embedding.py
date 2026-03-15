from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

from pydantic_ai.models.instrumented import InstrumentationSettings

from src.core.embedding import EmbeddingClient, _build_instrumentation_settings
from src.settings import OpenAISettings


def _make_openai_settings(**kwargs) -> OpenAISettings:
    base = {
        "API_KEY": "test-key",
        "EMBEDDING_MODEL": "text-embedding-3-small",
        "CHAT_MODEL": "openai:gpt-4o-mini",
    }
    base.update(kwargs)
    return OpenAISettings(**base)


def test_build_instrumentation_settings_disabled() -> None:
    settings = _make_openai_settings(EMBEDDING_INSTRUMENT=False)
    instrument = _build_instrumentation_settings(settings)
    assert instrument is False


def test_build_instrumentation_settings_enabled() -> None:
    settings = _make_openai_settings(
        EMBEDDING_INSTRUMENT=True,
        EMBEDDING_INSTRUMENT_INCLUDE_CONTENT=False,
        EMBEDDING_INSTRUMENT_INCLUDE_BINARY_CONTENT=False,
    )
    instrument = _build_instrumentation_settings(settings)
    assert isinstance(instrument, InstrumentationSettings)
    assert instrument.version == 2
    assert instrument.include_content is False
    assert instrument.include_binary_content is False


def test_embedding_client_sets_dimensions_from_settings() -> None:
    settings = _make_openai_settings(EMBEDDING_DIMENSIONS=1536)
    client = EmbeddingClient(settings)
    assert client._embedder._settings == {"dimensions": 1536}


async def test_embedding_client_embed_text_uses_embed_query() -> None:
    client = EmbeddingClient(_make_openai_settings())
    client._embedder = SimpleNamespace(
        embed_query=AsyncMock(return_value=SimpleNamespace(embeddings=[[0.1, 0.2, 0.3]]))
    )

    vector = await client.embed_text("What is ORO.FC.105?")

    assert vector == [0.1, 0.2, 0.3]
    client._embedder.embed_query.assert_called_once_with("What is ORO.FC.105?")


async def test_embedding_client_embed_texts_empty_returns_empty() -> None:
    client = EmbeddingClient(_make_openai_settings())
    client._embedder = SimpleNamespace(embed_documents=AsyncMock())

    vectors = await client.embed_texts([])

    assert vectors == []
    client._embedder.embed_documents.assert_not_called()


async def test_embedding_client_embed_texts_uses_embed_documents() -> None:
    client = EmbeddingClient(_make_openai_settings())
    client._embedder = SimpleNamespace(
        embed_documents=AsyncMock(return_value=SimpleNamespace(embeddings=[[0.1, 0.2], [0.3, 0.4]]))
    )

    vectors = await client.embed_texts(["doc 1", "doc 2"])

    assert vectors == [[0.1, 0.2], [0.3, 0.4]]
    client._embedder.embed_documents.assert_called_once_with(["doc 1", "doc 2"])


async def test_embedding_client_aexit_closes_provider_client() -> None:
    client = EmbeddingClient(_make_openai_settings())
    close = AsyncMock()
    client._provider = SimpleNamespace(client=SimpleNamespace(close=close))

    await client.__aexit__(None, None, None)

    close.assert_called_once_with()
