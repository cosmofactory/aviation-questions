import uuid

from pydantic import Field

from src.core.schema import OrmModel
from src.questions.constants import DEFAULT_TOP_K, MAX_SUPPLEMENTARY_QUESTIONS, MAX_TOP_K


class QuestionRequest(OrmModel):
    question: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(default=DEFAULT_TOP_K, ge=1, le=MAX_TOP_K)
    follow_up_to_question_id: uuid.UUID | None = None


class SourceChunk(OrmModel):
    chunk_id: uuid.UUID
    text: str
    citation: str | None
    section_path: str | None
    heading: str | None
    document_title: str
    jurisdiction: str
    doc_type: str
    distance: float


class AnswerResult(OrmModel):
    """Structured output from the PydanticAI agent."""

    answer: str
    citations: list[str]


class QuestionResponse(OrmModel):
    question_id: uuid.UUID
    root_question_id: uuid.UUID
    follow_up_index: int = Field(ge=0, le=MAX_SUPPLEMENTARY_QUESTIONS)
    supplementary_questions_remaining: int = Field(ge=0, le=MAX_SUPPLEMENTARY_QUESTIONS)
    answer: str
    citations: list[str]
    sources: list[SourceChunk]
    model: str
