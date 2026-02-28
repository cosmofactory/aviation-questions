import uuid

from src.core.schema import OrmModel


class DocumentUploadResponse(OrmModel):
    document_id: uuid.UUID
    chunk_count: int
    s3_key: str
    warnings: list[str]
