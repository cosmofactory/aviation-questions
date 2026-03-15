from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.base_dao import BaseDAO
from src.questions.models import QuestionLog


class QuestionLogDAO(BaseDAO):
    model = QuestionLog

    @classmethod
    async def count_supplementary_questions(
        cls,
        session: AsyncSession,
        root_question_id: uuid.UUID,
    ) -> int:
        stmt = select(func.count(cls.model.id)).where(
            cls.model.root_question_id == root_question_id,
            cls.model.follow_up_index > 0,
        )
        result = await session.execute(stmt)
        return int(result.scalar_one())

    @classmethod
    async def get_conversation_history(
        cls,
        session: AsyncSession,
        root_question_id: uuid.UUID,
    ) -> list[QuestionLog]:
        return await cls.get_all(
            session,
            cls.model.root_question_id == root_question_id,
            order_by=[cls.model.created_at.asc()],
        )
