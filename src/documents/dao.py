from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.base_dao import BaseDAO
from src.documents.models import Document, DocumentChunk, IngestionRun


class DocumentDAO(BaseDAO):
    model = Document


class DocumentChunkDAO(BaseDAO):
    model = DocumentChunk

    @classmethod
    async def search_similar(
        cls,
        session: AsyncSession,
        query_embedding: list[float],
        top_k: int = 5,
    ) -> list[tuple[DocumentChunk, float]]:
        """Find the top-k most similar chunks using cosine distance.

        Returns (chunk, distance) tuples ordered by ascending distance
        (lower = more similar).
        """
        distance = DocumentChunk.embedding.cosine_distance(query_embedding).label("distance")
        stmt = (
            select(DocumentChunk, distance)
            .where(DocumentChunk.embedding.is_not(None))
            .order_by(distance)
            .limit(top_k)
        )
        result = await session.execute(stmt)
        return [(row[0], row[1]) for row in result.all()]


class IngestionRunDAO(BaseDAO):
    model = IngestionRun
