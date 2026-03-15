import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
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
    assert response.follow_up_index == 0
    assert response.supplementary_questions_remaining == 3
    assert response.question_id == response.root_question_id

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
    assert log.parent_question_id is None
    assert log.follow_up_index == 0
    assert log.root_question_id == log.id


async def test_ask_with_no_chunks(
    session: AsyncSession, mock_embedding_client: AsyncMock, override_qa_agent: None
):
    """When no chunks are found, the agent is still called and sources is empty."""
    with patch(
        "src.questions.service.DocumentService.search_similar_chunks",
        new_callable=AsyncMock,
        return_value=[],
    ):
        response = await QuestionService.ask(
            session=session,
            embedding_client=mock_embedding_client,
            question="Unknown topic?",
            top_k=5,
        )

    assert response.sources == []
    assert response.citations == []


async def test_follow_up_includes_history_in_prompt(
    session: AsyncSession, mock_embedding_client: AsyncMock, override_qa_agent: None
):
    """Follow-up prompts include prior Q&A context and use enriched embedding query."""
    chunks = make_mock_chunks(1)

    with patch(
        "src.questions.service.DocumentService.search_similar_chunks",
        new_callable=AsyncMock,
        return_value=chunks,
    ):
        initial = await QuestionService.ask(
            session=session,
            embedding_client=mock_embedding_client,
            question="What is an apple?",
            top_k=5,
        )

        follow_up = await QuestionService.ask(
            session=session,
            embedding_client=mock_embedding_client,
            question="What kinds are there?",
            top_k=5,
            follow_up_to_question_id=initial.question_id,
        )

    assert follow_up.follow_up_index == 1
    assert follow_up.supplementary_questions_remaining == 2
    assert follow_up.root_question_id == initial.root_question_id

    embed_calls = mock_embedding_client.embed_text.call_args_list
    assert len(embed_calls) == 2
    second_query = embed_calls[1].args[0]
    assert "Previous question: What is an apple?" in second_query
    assert "Current follow-up question: What kinds are there?" in second_query


async def test_follow_up_limit_enforced(
    session: AsyncSession, mock_embedding_client: AsyncMock, override_qa_agent: None
):
    """At most three supplementary questions can be asked per root question."""
    chunks = make_mock_chunks(1)

    with patch(
        "src.questions.service.DocumentService.search_similar_chunks",
        new_callable=AsyncMock,
        return_value=chunks,
    ):
        root = await QuestionService.ask(
            session=session,
            embedding_client=mock_embedding_client,
            question="Root question",
            top_k=5,
        )

        previous_question_id = root.question_id
        for index in range(1, 4):
            follow_up = await QuestionService.ask(
                session=session,
                embedding_client=mock_embedding_client,
                question=f"Follow-up {index}",
                top_k=5,
                follow_up_to_question_id=previous_question_id,
            )
            previous_question_id = follow_up.question_id

        with pytest.raises(HTTPException) as exc_info:
            await QuestionService.ask(
                session=session,
                embedding_client=mock_embedding_client,
                question="Fourth follow-up",
                top_k=5,
                follow_up_to_question_id=previous_question_id,
            )

    assert exc_info.value.status_code == 403
    assert "Maximum supplementary questions reached" in str(exc_info.value.detail)
    assert mock_embedding_client.embed_text.call_count == 4


async def test_follow_up_parent_not_found(
    session: AsyncSession, mock_embedding_client: AsyncMock, override_qa_agent: None
):
    """Follow-up fails with 404 when parent question id does not exist."""
    with pytest.raises(HTTPException) as exc_info:
        await QuestionService.ask(
            session=session,
            embedding_client=mock_embedding_client,
            question="Follow-up with bad parent",
            top_k=5,
            follow_up_to_question_id=uuid.uuid4(),
        )

    assert exc_info.value.status_code == 404
