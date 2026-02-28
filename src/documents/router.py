from __future__ import annotations

import json
from datetime import date

from fastapi import APIRouter, Form, UploadFile

from src.core.dependencies import S3ClientDep
from src.core.sessions import WriteDBSession
from src.documents.enums import DocType, Jurisdiction
from src.documents.schemas import DocumentUploadResponse
from src.documents.service import DocumentService

router = APIRouter()


@router.post("/upload", response_model=DocumentUploadResponse, status_code=201)
async def upload_document(
    file: UploadFile,
    session: WriteDBSession,
    s3_client: S3ClientDep,
    title: str = Form(...),
    jurisdiction: Jurisdiction = Form(...),
    doc_type: DocType = Form(...),
    language: str = Form(default="en"),
    version_label: str | None = Form(default=None),
    effective_from: date | None = Form(default=None),
    effective_to: date | None = Form(default=None),
    published_at: date | None = Form(default=None),
    source_uri: str | None = Form(default=None),
    metadata: str | None = Form(default=None),
) -> DocumentUploadResponse:
    parsed_metadata = json.loads(metadata) if metadata else None

    return await DocumentService.upload_document(
        session=session,
        s3_client=s3_client,
        file=file,
        title=title,
        jurisdiction=jurisdiction.value,
        doc_type=doc_type.value,
        source_type="odt",
        language=language,
        version_label=version_label,
        effective_from=effective_from,
        effective_to=effective_to,
        published_at=published_at,
        source_uri=source_uri,
        metadata=parsed_metadata,
    )
