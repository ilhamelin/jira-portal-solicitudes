from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class JiraIssueResponse(BaseModel):
    id: str = Field(min_length=1, max_length=50)
    key: str = Field(min_length=1, max_length=50)


class JiraSyncResponse(JiraIssueResponse):
    fields: dict[str, Any] = Field(default_factory=dict)


class SyncResultResponse(BaseModel):
    solicitud_id: str
    jira_issue_key: str
    estado_anterior: str
    estado_nuevo: str
    responsable_jira: str | None
    hubo_cambios: bool


class BulkSyncResponse(BaseModel):
    total_revisadas: int
    total_actualizadas: int
    detalles: list[SyncResultResponse]
    timestamp: datetime
