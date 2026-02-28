from unittest.mock import AsyncMock, patch

from httpx import AsyncClient
from sqlalchemy import select

from src.documents.dao import DocumentChunkDAO
from src.documents.models import Document, DocumentChunk
from tests.conftest import test_session_factory
from tests.documents.conftest import create_test_odt

UPLOAD_URL = "/documents/upload"
REQUIRED_FIELDS = {
    "title": "Test Regulation",
    "jurisdiction": "easa",
    "doc_type": "regulation",
}


def _odt_with_content() -> bytes:
    return create_test_odt(
        [
            ("Chapter 1", 1, ["This is the first paragraph.", "This is the second paragraph."]),
            ("Section 1.1", 2, ["Details about section 1.1 go here."]),
            ("ORO.FC.105 Crew requirements", 1, ["Crew must comply with this regulation."]),
        ]
    )


async def test_reject_non_odt(ac: AsyncClient):
    response = await ac.post(
        UPLOAD_URL,
        files={"file": ("test.pdf", b"fake pdf content", "application/pdf")},
        data=REQUIRED_FIELDS,
    )
    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]


async def test_reject_oversized_file(ac: AsyncClient):
    # 26 MB of zeros
    oversized = b"\x00" * (26 * 1024 * 1024)
    response = await ac.post(
        UPLOAD_URL,
        files={"file": ("big.odt", oversized, "application/octet-stream")},
        data=REQUIRED_FIELDS,
    )
    assert response.status_code == 413
    assert "too large" in response.json()["detail"]


async def test_upload_odt_creates_document_and_chunks(ac: AsyncClient, mock_s3: AsyncMock):
    odt_bytes = _odt_with_content()

    response = await ac.post(
        UPLOAD_URL,
        files={"file": ("test_reg.odt", odt_bytes, "application/octet-stream")},
        data=REQUIRED_FIELDS,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["chunk_count"] > 0
    assert "test_reg.odt" in data["s3_key"]
    assert data["warnings"] == []

    # Verify S3 upload was called
    mock_s3.upload.assert_called_once()

    # Verify document and chunks in DB
    doc_id = data["document_id"]
    async with test_session_factory() as s:
        result = await s.execute(select(Document).where(Document.id == doc_id))
        doc = result.scalars().first()
        assert doc is not None
        assert doc.title == "Test Regulation"
        assert doc.s3_key == data["s3_key"]

        result = await s.execute(
            select(DocumentChunk).where(DocumentChunk.document_id == doc_id)
        )
        chunks = result.scalars().all()
        assert len(chunks) == data["chunk_count"]


async def test_duplicate_upload_returns_existing(ac: AsyncClient, mock_s3: AsyncMock):
    odt_bytes = _odt_with_content()

    # First upload
    resp1 = await ac.post(
        UPLOAD_URL,
        files={"file": ("test_dup.odt", odt_bytes, "application/octet-stream")},
        data=REQUIRED_FIELDS,
    )
    assert resp1.status_code == 201

    # Reset mock to track second call
    mock_s3.upload.reset_mock()

    # Second upload with same content
    resp2 = await ac.post(
        UPLOAD_URL,
        files={"file": ("test_dup.odt", odt_bytes, "application/octet-stream")},
        data=REQUIRED_FIELDS,
    )
    assert resp2.status_code == 201
    data2 = resp2.json()
    assert data2["document_id"] == resp1.json()["document_id"]
    assert "Duplicate" in data2["warnings"][0]

    # S3 should NOT be called for duplicate
    mock_s3.upload.assert_not_called()


async def test_s3_cleanup_on_db_failure(ac: AsyncClient, mock_s3: AsyncMock):
    odt_bytes = create_test_odt(
        [
            ("Unique Heading", 1, ["Unique content for cleanup test."]),
        ]
    )

    with patch.object(
        DocumentChunkDAO, "bulk_create", side_effect=RuntimeError("Simulated DB error")
    ):
        response = await ac.post(
            UPLOAD_URL,
            files={"file": ("fail_test.odt", odt_bytes, "application/octet-stream")},
            data=REQUIRED_FIELDS,
        )

    assert response.status_code == 500

    # S3 delete should have been called for cleanup
    mock_s3.delete.assert_called_once()
