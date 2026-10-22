from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SolicitudCreate(BaseModel):
    titulo: str = Field(min_length=5, max_length=200)
    descripcion: str = Field(min_length=10)
    tipo: Literal["incidente", "mejora"]
    area: str = Field(min_length=2, max_length=100)
    prioridad_solicitada: Literal["baja", "media", "alta", "urgente"] = "media"


class JiraIntegracionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    jira_issue_key: str | None
    estado_integracion: str
    ultima_sincronizacion_at: datetime | None


class SolicitudResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    titulo: str
    tipo: str
    area: str
    prioridad_solicitada: str
    prioridad_definitiva: str | None
    estado_negocio: str
    responsable_jira: str | None
    created_at: datetime
    jira_integracion: JiraIntegracionSchema | None


class SolicitudDetailResponse(SolicitudResponse):
    descripcion: str
    autor_email: str
    autor_nombre: str
    intentos_recientes: list[dict] = Field(default_factory=list)
