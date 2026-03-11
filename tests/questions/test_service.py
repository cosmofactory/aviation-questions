from unittest.mock import AsyncMock, patch

from pydantic_ai import capture_run_messages
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.questions.models import QuestionLog
from src.questions.service import QuestionService
from tests.questions.conftest import make_mock_chunks


async def test_ask_returns_structured_response(
    session: AsyncSession, mock_embedding_client: AsyncMock, override_qa_agent: None
):
    """QuestionService.ask returns a QuestionResponse with answer, citations, sources."""
    chunks = make_mock_chunks(2)

    with patch(
        "src.questions.service.DocumentService.search_similar_chunks",
        new_callable=AsyncMock,
        return_value=chunks,
    ):
        response = await QuestionService.ask(
            session=session,
            embedding_client=mock_embedding_client,
            question="What are crew requirements?",
            top_k=5,
        )

    assert isinstance(response.answer, str)
    assert len(response.answer) > 0
    assert isinstance(response.citations, list)
    assert len(response.sources) == 2
    assert response.sources[0].citation == "ORO.FC.101(a)"

    # Verify embedding was called
    mock_embedding_client.embed_text.assert_called_once_with("What are crew requirements?")


async def test_ask_logs_interaction(
    session: AsyncSession, mock_embedding_client: AsyncMock, override_qa_agent: None
):
    """QuestionService.ask creates a QuestionLog entry."""
    chunks = make_mock_chunks(1)

    with patch(
        "src.questions.service.DocumentService.search_similar_chunks",
        new_callable=AsyncMock,
        return_value=chunks,
    ):
        await QuestionService.ask(
            session=session,
            embedding_client=mock_embedding_client,
            question="Test logging question",
            top_k=3,
        )

    result = await session.execute(
        select(QuestionLog).where(QuestionLog.question == "Test logging question")
    )
    log = result.scalars().first()
    assert log is not None
    assert len(log.answer) > 0
    assert isinstance(log.citations, list)
    assert log.top_k == 3


async def test_ask_with_no_chunks(
    session: AsyncSession, mock_embedding_client: AsyncMock, override_qa_agent: None
):
    """When no chunks are found, the agent is still called and sources is empty."""
    with (
        capture_run_messages() as messages,
        patch(
            "src.questions.service.DocumentService.search_similar_chunks",
            new_callable=AsyncMock,
            return_value=[],
        ),
    ):
        response = await QuestionService.ask(
            session=session,
            embedding_client=mock_embedding_client,
            question="Unknown topic?",
            top_k=5,
        )

    assert response.sources == []
    # The user prompt sent to the agent should mention "No relevant documents"
    user_prompt = messages[0].parts[-1].content
    assert isinstance(user_prompt, str)
    assert "No relevant documents" in user_prompt
