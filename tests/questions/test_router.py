from unittest.mock import AsyncMock, patch

from httpx import AsyncClient

from tests.questions.conftest import make_mock_chunks

ASK_URL = "/questions/ask"


async def test_ask_returns_answer(ac: AsyncClient, override_qa_agent: None):
    """POST /questions/ask returns structured answer with citations and sources."""
    chunks = make_mock_chunks(2)

    with patch(
        "src.questions.service.DocumentService.search_similar_chunks",
        new_callable=AsyncMock,
        return_value=chunks,
    ):
        response = await ac.post(ASK_URL, json={"question": "What are crew requirements?"})

    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert isinstance(data["citations"], list)
    assert len(data["sources"]) == 2
    assert data["sources"][0]["citation"] == "ORO.FC.101(a)"
    assert "model" in data


async def test_ask_no_chunks_still_answers(ac: AsyncClient, override_qa_agent: None):
    """When no chunks are found, the agent still produces an answer."""
    with patch(
        "src.questions.service.DocumentService.search_similar_chunks",
        new_callable=AsyncMock,
        return_value=[],
    ):
        response = await ac.post(ASK_URL, json={"question": "Unknown question?"})

    assert response.status_code == 200
    data = response.json()
    assert data["sources"] == []
    assert "answer" in data


async def test_ask_validation_error_empty_question(ac: AsyncClient):
    """Empty question triggers validation error."""
    response = await ac.post(ASK_URL, json={"question": ""})
    assert response.status_code == 422


async def test_ask_validation_error_top_k_too_large(ac: AsyncClient):
    """top_k > MAX_TOP_K triggers validation error."""
    response = await ac.post(ASK_URL, json={"question": "test?", "top_k": 100})
    assert response.status_code == 422


async def test_ask_custom_top_k(ac: AsyncClient, override_qa_agent: None):
    """Custom top_k is passed through to the service."""
    chunks = make_mock_chunks(1)

    with patch(
        "src.questions.service.DocumentService.search_similar_chunks",
        new_callable=AsyncMock,
        return_value=chunks,
    ) as mock_search:
        response = await ac.post(ASK_URL, json={"question": "test?", "top_k": 10})

    assert response.status_code == 200
    mock_search.assert_called_once()
    call_args = mock_search.call_args
    assert call_args[0][2] == 10 or call_args.kwargs.get("top_k") == 10
