from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, Uuid, func
from sqlalchemy.dialects.postgresql import ENUM, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.database import Base

if TYPE_CHECKING:
    from .solicitud import Solicitud

ESTADO_INTEGRACION = ENUM(
    "pendiente", "sincronizado", "fallido", "reintentando",
    name="estado_integracion_tipo", create_type=False,
)
OPERACION = ENUM(
    "CREATE_ISSUE", "SYNC_STATUS", "UPDATE_PRIORITY",
    name="operacion_integracion_tipo", create_type=False,
)


class JiraIntegracion(Base):
    __tablename__ = "jira_integraciones"
    __table_args__ = (
        Index("idx_jira_integraciones_key", "jira_issue_key"),
        Index("idx_jira_integraciones_estado", "estado_integracion"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    solicitud_id: Mapped[UUID] = mapped_column(ForeignKey("solicitudes.id", ondelete="CASCADE"), unique=True)
    jira_issue_id: Mapped[str | None] = mapped_column(String(50))
    jira_issue_key: Mapped[str | None] = mapped_column(String(50))
    estado_integracion: Mapped[str] = mapped_column(ESTADO_INTEGRACION, default="pendiente", server_default="pendiente")
    ultima_sincronizacion_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    solicitud: Mapped[Solicitud] = relationship(back_populates="jira_integracion", lazy="raise")


class IntentoIntegracion(Base):
    __tablename__ = "intentos_integracion"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    solicitud_id: Mapped[UUID] = mapped_column(ForeignKey("solicitudes.id", ondelete="CASCADE"))
    operacion: Mapped[str] = mapped_column(OPERACION)
    http_status: Mapped[int | None] = mapped_column(Integer)
    error_mensaje: Mapped[str | None] = mapped_column(Text)
    payload_respuesta: Mapped[Any | None] = mapped_column(JSON().with_variant(JSONB(), "postgresql"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    solicitud: Mapped[Solicitud] = relationship(back_populates="intentos", lazy="raise")
