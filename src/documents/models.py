"""
RAG models for aviation-law document retrieval.

Stores ingested aviation documents (regulations, manuals, guidance material),
their chunked text with pgvector embeddings, and ETL run history.

Required Postgres extensions (run once per database):
    CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- gen_random_uuid()
    CREATE EXTENSION IF NOT EXISTS "vector";      -- pgvector column type + indexes
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.models import TimeStampedModel
from src.documents.constants import EMBEDDING_DIM
from src.documents.enums import DocType, IngestionStatus, Jurisdiction, SourceType

# ---------------------------------------------------------------------------
# 1) documents — one row per ingested aviation-law document version.
# ---------------------------------------------------------------------------


class Document(TimeStampedModel):
    """
    A single version of an aviation-law document.

    Versioning: each amendment or revision is a separate row.  Use
    ``effective_from`` / ``effective_to`` to determine which version was
    "in force" at a given date.  ``effective_to IS NULL`` means the document
    is currently in force.
    """

    __tablename__ = "documents"

    # -- identity --
    title: Mapped[str] = mapped_column(
        String(500),
        comment="Human-readable document title, e.g. 'Regulation (EU) 965/2012'",
    )
    source_type: Mapped[SourceType] = mapped_column(
        Enum(SourceType, name="source_type", native_enum=True, create_constraint=True, values_callable=lambda e: [x.value for x in e]),
        comment="Original file format before ingestion",
    )
    source_uri: Mapped[str | None] = mapped_column(
        String(2048),
        nullable=True,
        comment="Original location (URL, S3 key, file path) of the source file",
    )

    # -- classification --
    jurisdiction: Mapped[Jurisdiction] = mapped_column(
        Enum(Jurisdiction, name="jurisdiction", native_enum=True, create_constraint=True, values_callable=lambda e: [x.value for x in e]),
        comment="Regulatory body that issued the document",
    )
    doc_type: Mapped[DocType] = mapped_column(
        Enum(DocType, name="doc_type", native_enum=True, create_constraint=True, values_callable=lambda e: [x.value for x in e]),
        comment="Functional category: regulation, manual, guidance, etc.",
    )
    language: Mapped[str] = mapped_column(
        String(10),
        server_default=text("'en'"),
        comment="ISO 639-1 language code, e.g. 'en', 'fr', 'de'",
    )

    # -- versioning --
    version_label: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Human label like 'Amendment 12' or 'v3.4'",
    )
    effective_from: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="Date the document version enters into force",
    )
    effective_to: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="Date the document version is superseded (NULL = still in force)",
    )
    published_at: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="Official publication date",
    )

    # -- deduplication --
    checksum: Mapped[str] = mapped_column(
        String(128),
        comment="SHA-256 of the canonical source file; used for deduplication",
    )

    # -- S3 storage --
    s3_bucket: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="S3 bucket where the source file is stored",
    )
    s3_key: Mapped[str | None] = mapped_column(
        String(2048),
        nullable=True,
        comment="S3 object key for the source file",
    )
    file_size: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Size of the source file in bytes",
    )
    content_type: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="MIME type of the source file",
    )

    # -- flexible metadata --
    metadata_: Mapped[dict | None] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
        server_default=text("'{}'::jsonb"),
        comment="Arbitrary extra fields (issuing authority, CELEX number, etc.)",
    )

    # -- relationships --
    chunks: Mapped[list[DocumentChunk]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
        order_by="DocumentChunk.chunk_index",
    )
    ingestion_runs: Mapped[list[IngestionRun]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="noload",
    )

    # -- table-level constraints and indexes --
    __table_args__ = (
        # Deduplication: same file content should not be stored twice.
        UniqueConstraint("checksum", name="uq_documents_checksum"),
        # Filter by jurisdiction + doc_type (most common query pattern).
        Index("ix_documents_jurisdiction_doc_type", "jurisdiction", "doc_type"),
        # "In force" queries: WHERE effective_from <= :date AND (effective_to IS NULL OR effective_to > :date)
        Index("ix_documents_effective_range", "effective_from", "effective_to"),
        # GIN index for JSONB containment queries (@>, ?, ?|, ?& operators).
        Index("ix_documents_metadata", "metadata", postgresql_using="gin"),
        # Validity: effective_to must be after effective_from when both are set.
        CheckConstraint(
            "effective_to IS NULL OR effective_from IS NULL OR effective_to > effective_from",
            name="ck_documents_effective_range",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<Document id={self.id!s:.8} title={self.title!r} "
            f"jurisdiction={self.jurisdiction.value} doc_type={self.doc_type.value}>"
        )


# ---------------------------------------------------------------------------
# 2) document_chunks — text fragments with embeddings for vector search.
# ---------------------------------------------------------------------------


class DocumentChunk(TimeStampedModel):
    """
    A single text chunk extracted from a Document.

    Each chunk stores:
    - the raw text (for quoting in answers),
    - a dense embedding vector (for ANN search via pgvector),
    - structural metadata (section path, citation, heading) so the UI
      can show where in the document the answer came from.
    """

    __tablename__ = "document_chunks"

    # -- parent document --
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        comment="Parent document this chunk belongs to",
    )

    # -- ordering --
    chunk_index: Mapped[int] = mapped_column(
        Integer,
        comment="0-based position of this chunk within the document",
    )

    # -- structural context --
    section_path: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
        comment="Hierarchical path, e.g. 'Part-ORO > Subpart FC > ORO.FC.105'",
    )
    citation: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Canonical citation label, e.g. 'Reg (EU) 965/2012, ORO.FC.105(a)'",
    )
    heading: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Local heading or section title at this chunk's level",
    )

    # -- content --
    text: Mapped[str] = mapped_column(
        Text,
        comment="Raw chunk text, used for quoting in RAG answers",
    )
    token_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Approximate token count (model-specific); useful for context-window budgeting",
    )

    # -- deduplication --
    checksum: Mapped[str] = mapped_column(
        String(128),
        comment="SHA-256 of the chunk text; prevents re-embedding identical content",
    )

    # -- embedding --
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(EMBEDDING_DIM),
        nullable=True,
        comment=f"Dense vector ({EMBEDDING_DIM}-dim) for approximate nearest-neighbor search",
    )
    embedding_model: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="Identifier of the embedding model used, e.g. 'text-embedding-3-small'",
    )

    # -- relationships --
    document: Mapped[Document] = relationship(
        back_populates="chunks",
    )

    # -- table-level constraints and indexes --
    __table_args__ = (
        # Each chunk position is unique within a document.
        UniqueConstraint("document_id", "chunk_index", name="uq_chunks_doc_index"),
        # Fast lookup by parent document.
        Index("ix_chunks_document_id", "document_id"),
        # Citation search (exact or prefix match).
        Index("ix_chunks_citation", "citation"),
        # Deduplication lookups.
        Index("ix_chunks_checksum", "checksum"),
        # HNSW vector index for fast approximate nearest-neighbor queries.
        # HNSW is preferred over IVFFlat because it does not require a separate
        # training step and gives better recall at comparable speed.
        # vector_cosine_ops → cosine distance, the standard for normalized embeddings.
        Index(
            "ix_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 200},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<DocumentChunk id={self.id!s:.8} doc={self.document_id!s:.8} "
            f"idx={self.chunk_index} citation={self.citation!r}>"
        )


# ---------------------------------------------------------------------------
# 3) ingestion_runs — ETL audit trail for debugging and reprocessing.
# ---------------------------------------------------------------------------


class IngestionRun(TimeStampedModel):
    """
    Tracks a single ETL run that ingests (or re-ingests) a document.

    Used for:
    - debugging failed ingestions,
    - knowing when a document was last refreshed,
    - recording chunk-level statistics (via ``stats`` JSONB).
    """

    __tablename__ = "ingestion_runs"

    # -- run metadata --
    status: Mapped[IngestionStatus] = mapped_column(
        Enum(IngestionStatus, name="ingestion_status", native_enum=True, create_constraint=True, values_callable=lambda e: [x.value for x in e]),
        server_default=text("'started'"),
        comment="Lifecycle state: started → success | failed",
    )
    source_uri: Mapped[str] = mapped_column(
        String(2048),
        comment="URI of the source being ingested in this run",
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=True,
        comment="Linked document (set after successful creation/update)",
    )

    # -- timing --
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="When the run began",
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When the run completed (success or failure)",
    )

    # -- diagnostics --
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Error traceback or message if the run failed",
    )
    stats: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        server_default=text("'{}'::jsonb"),
        comment="Run statistics: chunk_count, token_total, duration_s, etc.",
    )

    # -- relationships --
    document: Mapped[Document | None] = relationship(
        back_populates="ingestion_runs",
    )

    # -- indexes --
    __table_args__ = (
        Index("ix_ingestion_runs_document_id", "document_id"),
        Index("ix_ingestion_runs_status", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<IngestionRun id={self.id!s:.8} status={self.status.value} "
            f"source={self.source_uri!r:.60}>"
        )
