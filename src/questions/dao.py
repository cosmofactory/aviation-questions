from src.core.base_dao import BaseDAO
from src.questions.models import QuestionLog


class QuestionLogDAO(BaseDAO):
    model = QuestionLog
