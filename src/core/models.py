import datetime

from sqlalchemy import DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from src.core.engine import Base


class TimeStampedModel(Base):
    """
    Abstract model for universal and timestamp columns.

    created_at - timestamp of creation,
    updated_at - timestamp of last update, autoupdates on every update,
    """

    __abstract__ = True

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True
    )
