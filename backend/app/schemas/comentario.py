from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator


class ComentarioCreate(BaseModel):
    contenido: str = Field(min_length=2, max_length=2000)

    @field_validator("contenido", mode="before")
    @classmethod
    def trim_content(cls, value):
        return value.strip() if isinstance(value, str) else value


class ComentarioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    solicitud_id: UUID
    autor_nombre: str
    origen: Literal["portal", "jira"]
    contenido: str
    jira_comment_id: str | None
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def utc_timestamp(cls, value: datetime) -> datetime:
        # SQLite pierde tzinfo; las fechas guardadas por el servicio están en UTC.
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class JiraCommentAuthor(BaseModel):
    displayName: str = Field(min_length=1, max_length=150)


class JiraCommentProperty(BaseModel):
    key: str
    value: object = None


class JiraComment(BaseModel):
    id: str = Field(pattern=r"^[0-9]{1,50}$")
    body: dict
    author: JiraCommentAuthor
    created: AwareDatetime
    visibility: dict | None = None
    properties: list[JiraCommentProperty] = Field(default_factory=list)


class JiraCommentPage(BaseModel):
    comments: list[JiraComment]
    startAt: int = Field(ge=0, strict=True)
    total: int = Field(ge=0, strict=True)
