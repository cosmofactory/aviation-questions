from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi import HTTPException, status
from pydantic_ai import Agent, RunContext, Tool, UsageLimits
from pydantic_ai.tools import ToolDefinition
from pydantic_ai.toolsets import FunctionToolset
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.embedding import EmbeddingClient
from src.documents.service import DocumentService
from src.questions.constants import MAX_SUPPLEMENTARY_QUESTIONS, SYSTEM_PROMPT
from src.questions.dao import QuestionLogDAO
from src.questions.models import QuestionLog
from src.questions.schemas import AnswerResult, QuestionResponse, SourceChunk
from src.settings import settings


@dataclass(slots=True)
class QAAgentDeps:
    question: str
    conversation_context: str | None
    source_chunks: list[SourceChunk]

    @property
    def available_citations(self) -> list[str]:
        citations: list[str] = []
        for chunk in self.source_chunks:
            if chunk.citation and chunk.citation not in citations:
                citations.append(chunk.citation)
        return citations


def _list_retrieved_sources(ctx: RunContext[QAAgentDeps]) -> list[SourceChunk]:
    """Return all pre-retrieved source chunks for the current question."""
    return ctx.deps.source_chunks


def _get_source_by_citation(ctx: RunContext[QAAgentDeps], citation: str) -> SourceChunk | None:
    """Return a single retrieved source chunk matching a citation label."""
    normalized = citation.strip()
    if not normalized:
        return None

    for chunk in ctx.deps.source_chunks:
        if chunk.citation == normalized:
            return chunk
    return None


def _get_conversation_history(ctx: RunContext[QAAgentDeps]) -> str | None:
    """Return prior Q&A turns when this question is a follow-up."""
    return ctx.deps.conversation_context


QA_TOOLSET = FunctionToolset(
    tools=[
        Tool(
            _list_retrieved_sources,
            name="list_retrieved_sources",
            description="Get the retrieved aviation-law chunks for this question.",
            takes_ctx=True,
            sequential=True,
        ),
        Tool(
            _get_source_by_citation,
            name="get_source_by_citation",
            description="Lookup one retrieved chunk by citation label (e.g. ORO.FC.105(a)).",
            takes_ctx=True,
            sequential=True,
        ),
        Tool(
            _get_conversation_history,
            name="get_conversation_history",
            description="Get prior turns to resolve references in follow-up questions.",
            takes_ctx=True,
            sequential=True,
        ),
    ]
)


async def _prepare_qa_tools(
    ctx: RunContext[QAAgentDeps],
    tool_defs: list[ToolDefinition],
) -> list[ToolDefinition]:
    """Enable only tools relevant to the current run context."""
    has_conversation_context = bool(ctx.deps.conversation_context)
    has_citations = any(chunk.citation for chunk in ctx.deps.source_chunks)

    prepared: list[ToolDefinition] = []
    for tool_def in tool_defs:
        if tool_def.name == "get_conversation_history" and not has_conversation_context:
            continue
        if tool_def.name == "get_source_by_citation" and not has_citations:
            continue
        prepared.append(tool_def)
    return prepared


qa_agent: Agent[QAAgentDeps, AnswerResult] = Agent(
    output_type=AnswerResult,
    deps_type=QAAgentDeps,
    instructions=SYSTEM_PROMPT,
    toolsets=[QA_TOOLSET],
    prepare_tools=_prepare_qa_tools,
    defer_model_check=True,
    output_retries=2,
    tool_timeout=20.0,
)


@qa_agent.instructions
def _dynamic_instructions(ctx: RunContext[QAAgentDeps]) -> str:
    parts = [
        "Call `list_retrieved_sources` before writing your final answer.",
        "Use `get_source_by_citation` when you need exact clause wording.",
        "Use only citations returned by these tools.",
    ]

    if ctx.deps.conversation_context:
        parts.append(
            "Conversation history (for follow-up disambiguation only):\n"
            f"{ctx.deps.conversation_context}"
        )

    available_citations = ctx.deps.available_citations
    if available_citations:
        parts.append(f"Available citation labels: {', '.join(available_citations)}")
    else:
        parts.append(
            "No citation labels are available for this run; return an empty citations list."
        )

    return "\n\n".join(parts)


@qa_agent.output_validator
def _validate_output(ctx: RunContext[QAAgentDeps], output: AnswerResult) -> AnswerResult:
    output.answer = output.answer.strip()
    if not output.answer:
        output.answer = "The retrieved context is insufficient to answer this question."

    available_citations = ctx.deps.available_citations
    if not available_citations:
        output.citations = []
        return output

    seen: set[str] = set()
    validated_citations: list[str] = []
    for citation in output.citations:
        if citation in available_citations and citation not in seen:
            validated_citations.append(citation)
            seen.add(citation)

    # Enforce in-range citations and avoid empty citation lists when citations are available.
    output.citations = validated_citations or [available_citations[0]]
    return output


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

        source_chunks = [_to_source_chunk(chunk) for chunk in chunks]
        deps = QAAgentDeps(
            question=question,
            conversation_context=conversation_context,
            source_chunks=source_chunks,
        )

        # 4. Run PydanticAI agent
        result = await qa_agent.run(
            question,
            model=_get_model(),
            deps=deps,
            usage_limits=UsageLimits(request_limit=6, tool_calls_limit=6),
            metadata={
                "question_id": str(question_id),
                "root_question_id": str(root_question_id),
                "follow_up_index": follow_up_index,
                "top_k": top_k,
                "retrieved_chunks": len(source_chunks),
                "has_conversation_context": bool(conversation_context),
            },
        )
        answer_data: AnswerResult = result.output

        # 5. Build source chunks for response
        sources = source_chunks

        # 6. Log the interaction
        await QuestionLogDAO.create(
            session,
            id=question_id,
            question=question,
            answer=answer_data.answer,
            citations=answer_data.citations,
            source_chunk_ids=[str(chunk.chunk_id) for chunk in sources],
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


def _to_source_chunk(chunk: dict) -> SourceChunk:
    return SourceChunk(
        chunk_id=chunk["chunk_id"],
        text=chunk["text"],
        citation=chunk["citation"],
        section_path=chunk["section_path"],
        heading=chunk["heading"],
        document_title=chunk["document_title"],
        jurisdiction=chunk["jurisdiction"],
        doc_type=chunk["doc_type"],
        distance=chunk["distance"],
    )


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
