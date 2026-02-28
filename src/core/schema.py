from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ErrorResponse(BaseModel):
    detail: str


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class STimetampedModel(OrmModel):
    created_at: datetime
    updated_at: datetime


class PaginatedResponse(OrmModel):
    items: list[OrmModel]
    total: int
    limit: int
    size: int
