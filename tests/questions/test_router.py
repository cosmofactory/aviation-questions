import uuid
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
    assert data["follow_up_index"] == 0
    assert data["supplementary_questions_remaining"] == 3
    assert data["question_id"] == data["root_question_id"]
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
    assert data["supplementary_questions_remaining"] == 3


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


async def test_follow_ups_allowed_up_to_three(ac: AsyncClient, override_qa_agent: None):
    """A root question supports up to three supplementary follow-up questions."""
    chunks = make_mock_chunks(1)

    with patch(
        "src.questions.service.DocumentService.search_similar_chunks",
        new_callable=AsyncMock,
        return_value=chunks,
    ):
        root_response = await ac.post(ASK_URL, json={"question": "What is an apple?"})

        assert root_response.status_code == 200
        root_data = root_response.json()
        root_question_id = root_data["question_id"]
        previous_question_id = root_question_id

        for follow_up_index in range(1, 4):
            follow_up_response = await ac.post(
                ASK_URL,
                json={
                    "question": f"Follow-up {follow_up_index}?",
                    "follow_up_to_question_id": previous_question_id,
                },
            )
            assert follow_up_response.status_code == 200
            follow_up_data = follow_up_response.json()
            assert follow_up_data["root_question_id"] == root_data["root_question_id"]
            assert follow_up_data["follow_up_index"] == follow_up_index
            assert follow_up_data["supplementary_questions_remaining"] == 3 - follow_up_index
            previous_question_id = follow_up_data["question_id"]

        rejected_response = await ac.post(
            ASK_URL,
            json={
                "question": "Fourth supplementary question?",
                "follow_up_to_question_id": previous_question_id,
            },
        )

    assert rejected_response.status_code == 403


async def test_follow_up_parent_not_found(ac: AsyncClient, override_qa_agent: None):
    """Follow-up against unknown parent id returns 404."""
    response = await ac.post(
        ASK_URL,
        json={
            "question": "What about that?",
            "follow_up_to_question_id": str(uuid.uuid4()),
        },
    )

    assert response.status_code == 404
