from __future__ import annotations

import hashlib
import logging
from pathlib import PurePosixPath

from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.s3 import S3Client
from src.documents.chunker import DocumentChunker
from src.documents.constants import ALLOWED_EXTENSIONS, MAX_FILE_SIZE_BYTES, ODT_CONTENT_TYPE
from src.documents.dao import DocumentChunkDAO, DocumentDAO
from src.documents.models import Document
from src.documents.odt_parser import ODTParser
from src.documents.schemas import DocumentUploadResponse

logger = logging.getLogger(__name__)


class DocumentService:
    @staticmethod
    async def upload_document(
        session: AsyncSession,
        s3_client: S3Client,
        file: UploadFile,
        *,
        title: str,
        jurisdiction: str,
        doc_type: str,
        source_type: str,
        language: str = "en",
        version_label: str | None = None,
        effective_from: object = None,
        effective_to: object = None,
        published_at: object = None,
        source_uri: str | None = None,
        metadata: dict | None = None,
    ) -> DocumentUploadResponse:
        warnings: list[str] = []

        # 1. Validate extension
        filename = file.filename or "upload.odt"
        suffix = PurePosixPath(filename).suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type '{suffix}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
            )

        # 2. Read and validate size
        file_bytes = await file.read()
        if len(file_bytes) > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"File too large ({len(file_bytes)} bytes). Maximum: {MAX_FILE_SIZE_BYTES} bytes.",
            )

        # 3. Compute checksum for deduplication
        checksum = hashlib.sha256(file_bytes).hexdigest()

        # 4. Check for duplicate
        existing = await DocumentDAO.get_first(session, Document.checksum == checksum)
        if existing:
            chunk_count = len(existing.chunks) if existing.chunks else 0
            warnings.append("Duplicate document: file with identical content already exists.")
            return DocumentUploadResponse(
                document_id=existing.id,
                chunk_count=chunk_count,
                s3_key=existing.s3_key or "",
                warnings=warnings,
            )

        # 5. Parse ODT
        sections = ODTParser(file_bytes).parse()
        if not sections:
            warnings.append("Empty or unparseable document: no sections found.")

        # 6. Chunk
        chunks = DocumentChunker().chunk_sections(sections)
        has_headings = any(s.heading for s in sections)
        if not has_headings and sections:
            warnings.append("No headings detected; all content placed in a single section.")

        # 7. Upload to S3
        # Key uses checksum prefix for deduplication + original filename for readability
        s3_key = f"documents/{checksum}/{filename}"
        await s3_client.upload(key=s3_key, data=file_bytes, content_type=ODT_CONTENT_TYPE)

        try:
            # 8. Insert document
            document = await DocumentDAO.create(
                session,
                title=title,
                source_type=source_type,
                jurisdiction=jurisdiction,
                doc_type=doc_type,
                language=language,
                version_label=version_label,
                effective_from=effective_from,
                effective_to=effective_to,
                published_at=published_at,
                source_uri=source_uri,
                checksum=checksum,
                metadata_=metadata,
                s3_bucket=s3_client._bucket,
                s3_key=s3_key,
                file_size=len(file_bytes),
                content_type=ODT_CONTENT_TYPE,
            )

            # 9. Bulk insert chunks
            if chunks:
                chunk_dicts = [
                    {
                        "document_id": document.id,
                        "chunk_index": c.chunk_index,
                        "section_path": c.section_path,
                        "citation": c.citation,
                        "heading": c.heading,
                        "text": c.text,
                        "token_count": c.token_count,
                        "checksum": c.checksum,
                    }
                    for c in chunks
                ]
                await DocumentChunkDAO.bulk_create(session, chunk_dicts)

        except Exception as exc:
            # Best-effort S3 cleanup on DB failure
            try:
                await s3_client.delete(key=s3_key)
            except Exception:
                logger.exception("Failed to clean up S3 object %s after DB error", s3_key)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to persist document: {exc}",
            ) from exc

        return DocumentUploadResponse(
            document_id=document.id,
            chunk_count=len(chunks),
            s3_key=s3_key,
            warnings=warnings,
        )
