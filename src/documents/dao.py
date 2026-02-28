from src.core.base_dao import BaseDAO
from src.documents.models import Document, DocumentChunk, IngestionRun


class DocumentDAO(BaseDAO):
    model = Document


class DocumentChunkDAO(BaseDAO):
    model = DocumentChunk


class IngestionRunDAO(BaseDAO):
    model = IngestionRun
