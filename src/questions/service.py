from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from pydantic_ai import Agent
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.embedding import EmbeddingClient
from src.documents.service import DocumentService
from src.questions.constants import MAX_SUPPLEMENTARY_QUESTIONS, SYSTEM_PROMPT
from src.questions.dao import QuestionLogDAO
from src.questions.models import QuestionLog
from src.questions.schemas import AnswerResult, QuestionResponse, SourceChunk
from src.settings import settings

qa_agent: Agent[None, AnswerResult] = Agent(
    output_type=AnswerResult,
    system_prompt=SYSTEM_PROMPT,
    defer_model_check=True,
)


class QuestionService:
    @staticmethod
    async def ask(
        session: AsyncSession,
        embedding_client: EmbeddingClient,
        question: str,
        top_k: int = 5,
        follow_up_to_question_id: uuid.UUID | None = None,
    ) -> QuestionResponse:
        question_id = uuid.uuid4()

        # 1. Resolve follow-up context and limits
        (
            conversation_context,
            follow_up_index,
            root_question_id,
            retrieval_query,
        ) = await _resolve_follow_up_context(
            session=session,
            question=question,
            question_id=question_id,
            follow_up_to_question_id=follow_up_to_question_id,
        )

        # 2. Embed the retrieval query
        query_embedding = await embedding_client.embed_text(retrieval_query)

        # 3. Retrieve similar chunks via DocumentService
        chunks = await DocumentService.search_similar_chunks(session, query_embedding, top_k)

        # 4. Build context for the agent
        if not chunks:
            context_text = "No relevant documents were found for this question."
        else:
            context_parts: list[str] = []
            for i, c in enumerate(chunks, 1):
                header = f"[{i}] {c['document_title']}"
                if c["citation"]:
                    header += f" — {c['citation']}"
                context_parts.append(f"{header}\n{c['text']}")
            context_text = "\n\n---\n\n".join(context_parts)

        user_prompt = _build_user_prompt(
            question=question,
            context_text=context_text,
            conversation_context=conversation_context,
        )

        # 5. Run PydanticAI agent
        result = await qa_agent.run(user_prompt, model=_get_model())
        answer_data: AnswerResult = result.output

        # 6. Build source chunks for response
        sources = [
            SourceChunk(
                chunk_id=c["chunk_id"],
                text=c["text"],
                citation=c["citation"],
                section_path=c["section_path"],
                heading=c["heading"],
                document_title=c["document_title"],
                jurisdiction=c["jurisdiction"],
                doc_type=c["doc_type"],
                distance=c["distance"],
            )
            for c in chunks
        ]

        # 7. Log the interaction
        await QuestionLogDAO.create(
            session,
            id=question_id,
            question=question,
            answer=answer_data.answer,
            citations=answer_data.citations,
            source_chunk_ids=[c["chunk_id"] for c in chunks],
            model=settings.openai.CHAT_MODEL,
            top_k=top_k,
            root_question_id=root_question_id,
            parent_question_id=follow_up_to_question_id,
            follow_up_index=follow_up_index,
        )

        return QuestionResponse(
            question_id=question_id,
            root_question_id=root_question_id,
            follow_up_index=follow_up_index,
            supplementary_questions_remaining=MAX_SUPPLEMENTARY_QUESTIONS - follow_up_index,
            answer=answer_data.answer,
            citations=answer_data.citations,
            sources=sources,
            model=settings.openai.CHAT_MODEL,
        )


def _build_user_prompt(
    question: str,
    context_text: str,
    conversation_context: str | None,
) -> str:
    prompt_parts = [f"Context:\n{context_text}"]
    if conversation_context:
        prompt_parts.append(
            "Conversation history (use this only to resolve follow-up references):\n"
            f"{conversation_context}"
        )
    prompt_parts.append(f"Question: {question}")
    return "\n\n".join(prompt_parts)


async def _resolve_follow_up_context(
    session: AsyncSession,
    question: str,
    question_id: uuid.UUID,
    follow_up_to_question_id: uuid.UUID | None,
) -> tuple[str | None, int, uuid.UUID, str]:
    if follow_up_to_question_id is None:
        return None, 0, question_id, question

    parent = await QuestionLogDAO.get_by_id(session, follow_up_to_question_id)
    if parent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Follow-up question parent was not found.",
        )

    root_question_id = parent.root_question_id
    supplementary_count = await QuestionLogDAO.count_supplementary_questions(
        session, root_question_id
    )

    if supplementary_count >= MAX_SUPPLEMENTARY_QUESTIONS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Maximum supplementary questions reached ({MAX_SUPPLEMENTARY_QUESTIONS}) "
                "for this question thread."
            ),
        )

    history = await QuestionLogDAO.get_conversation_history(session, root_question_id)
    if not history:
        history = [parent]

    conversation_context = _build_conversation_context(history)
    retrieval_query = _build_follow_up_retrieval_query(question, parent)
    return conversation_context, supplementary_count + 1, root_question_id, retrieval_query


def _build_conversation_context(history: list[QuestionLog]) -> str:
    turns: list[str] = []
    for idx, log in enumerate(history, start=1):
        citations = ", ".join(log.citations) if log.citations else "None"
        turns.append(
            f"Turn {idx} question: {log.question}\n"
            f"Turn {idx} answer: {log.answer}\n"
            f"Turn {idx} citations: {citations}"
        )
    return "\n\n".join(turns)


def _build_follow_up_retrieval_query(question: str, parent: QuestionLog) -> str:
    return (
        "Follow-up query context:\n"
        f"Previous question: {parent.question}\n"
        f"Previous answer: {parent.answer}\n"
        f"Current follow-up question: {question}"
    )


def _get_model() -> Agent.RunModelType:
    """Build the OpenAI model at call time (avoids import-time API key validation)."""
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.openai import OpenAIProvider

    provider = OpenAIProvider(api_key=settings.openai.API_KEY)
    model_name = settings.openai.CHAT_MODEL.removeprefix("openai:")
    return OpenAIChatModel(model_name, provider=provider)
