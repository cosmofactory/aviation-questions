import datetime
import uuid

from sqlalchemy import DateTime, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from src.core.engine import Base


class TimeStampedModel(Base):
    """
    Abstract base model with UUID primary key and timezone-aware timestamps.

    Provides:
        id         - UUID v4 primary key, generated server-side via pgcrypto.
        created_at - timestamp of creation (server default).
        updated_at - timestamp of last update, auto-updates on every write.

    Requires the ``pgcrypto`` Postgres extension for ``gen_random_uuid()``.
    """

    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True
    )
