from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AdjuntoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    solicitud_id: UUID
    nombre_archivo: str
    mime_type: str
    tamanio_bytes: int
    jira_attachment_id: str | None
    created_at: datetime


class JiraAttachmentResponse(BaseModel):
    id: str = Field(pattern=r"^[0-9]{1,50}$")
    filename: str = Field(min_length=1, max_length=255)
    size: int = Field(ge=0, le=10 * 1024 * 1024)
    mimeType: str = Field(min_length=1, max_length=100)
    content: str | None = None
