from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, Uuid, func
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.database import Base

if TYPE_CHECKING:
    from .integracion import IntentoIntegracion, JiraIntegracion
    from .usuario import Usuario

TIPO_SOLICITUD = ENUM("incidente", "mejora", name="tipo_solicitud", create_type=False)
PRIORIDAD = ENUM("baja", "media", "alta", "urgente", name="prioridad_tipo", create_type=False)
ESTADO_NEGOCIO = ENUM(
    "Recibido", "En análisis", "En desarrollo", "En pruebas", "Cerrado", "Rechazado",
    name="estado_negocio_tipo", create_type=False,
)


class Solicitud(Base):
    __tablename__ = "solicitudes"
    __table_args__ = (
        Index("idx_solicitudes_autor", "autor_id"),
        Index("idx_solicitudes_estado", "estado_negocio"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    autor_id: Mapped[UUID] = mapped_column(ForeignKey("usuarios.id", ondelete="RESTRICT"))
    titulo: Mapped[str] = mapped_column(String(200))
    descripcion: Mapped[str] = mapped_column(Text)
    tipo: Mapped[str] = mapped_column(TIPO_SOLICITUD)
    area: Mapped[str] = mapped_column(String(100))
    prioridad_solicitada: Mapped[str] = mapped_column(PRIORIDAD, default="media", server_default="media")
    prioridad_definitiva: Mapped[str | None] = mapped_column(PRIORIDAD)
    estado_negocio: Mapped[str] = mapped_column(ESTADO_NEGOCIO, default="Recibido", server_default="Recibido")
    responsable_jira: Mapped[str | None] = mapped_column(String(150))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    autor: Mapped[Usuario] = relationship(back_populates="solicitudes", lazy="raise")
    jira_integracion: Mapped[JiraIntegracion | None] = relationship(
        back_populates="solicitud", lazy="raise", uselist=False, passive_deletes=True,
    )
    intentos: Mapped[list[IntentoIntegracion]] = relationship(
        back_populates="solicitud", lazy="raise", passive_deletes=True,
    )
