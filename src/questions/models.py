from __future__ import annotations

from sqlalchemy import Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.core.models import TimeStampedModel


class QuestionLog(TimeStampedModel):
    """Audit trail for RAG question-answering interactions."""

    __tablename__ = "question_logs"

    question: Mapped[str] = mapped_column(Text, comment="User's original question")
    answer: Mapped[str] = mapped_column(Text, comment="Generated answer")
    citations: Mapped[list] = mapped_column(
        JSONB, comment="List of citation strings from the answer"
    )
    source_chunk_ids: Mapped[list] = mapped_column(
        JSONB, comment="UUIDs of the retrieved context chunks"
    )
    model: Mapped[str] = mapped_column(String(200), comment="LLM model used for generation")
    top_k: Mapped[int] = mapped_column(Integer, comment="Number of chunks retrieved")
