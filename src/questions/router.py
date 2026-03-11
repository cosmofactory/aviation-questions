from fastapi import APIRouter

from src.core.dependencies import EmbeddingClientDep
from src.core.sessions import WriteDBSession
from src.questions.schemas import QuestionRequest, QuestionResponse
from src.questions.service import QuestionService

router = APIRouter()


@router.post("/ask", response_model=QuestionResponse)
async def ask_question(
    session: WriteDBSession,
    embedding_client: EmbeddingClientDep,
    data: QuestionRequest,
) -> QuestionResponse:
    return await QuestionService.ask(
        session=session,
        embedding_client=embedding_client,
        question=data.question,
        top_k=data.top_k,
    )
