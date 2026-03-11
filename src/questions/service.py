from __future__ import annotations

from pydantic_ai import Agent
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.embedding import EmbeddingClient
from src.documents.service import DocumentService
from src.questions.constants import SYSTEM_PROMPT
from src.questions.dao import QuestionLogDAO
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
    ) -> QuestionResponse:
        # 1. Embed the question
        query_embedding = await embedding_client.embed_text(question)

        # 2. Retrieve similar chunks via DocumentService
        chunks = await DocumentService.search_similar_chunks(session, query_embedding, top_k)

        # 3. Build context for the agent
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

        user_prompt = f"Context:\n{context_text}\n\nQuestion: {question}"

        # 4. Run PydanticAI agent
        result = await qa_agent.run(user_prompt, model=_get_model())
        answer_data: AnswerResult = result.output

        # 5. Build source chunks for response
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

        # 6. Log the interaction
        await QuestionLogDAO.create(
            session,
            question=question,
            answer=answer_data.answer,
            citations=answer_data.citations,
            source_chunk_ids=[c["chunk_id"] for c in chunks],
            model=settings.openai.CHAT_MODEL,
            top_k=top_k,
        )

        return QuestionResponse(
            answer=answer_data.answer,
            citations=answer_data.citations,
            sources=sources,
            model=settings.openai.CHAT_MODEL,
        )


def _get_model() -> Agent.RunModelType:
    """Build the OpenAI model at call time (avoids import-time API key validation)."""
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.openai import OpenAIProvider

    provider = OpenAIProvider(api_key=settings.openai.API_KEY)
    model_name = settings.openai.CHAT_MODEL.removeprefix("openai:")
    return OpenAIChatModel(model_name, provider=provider)
