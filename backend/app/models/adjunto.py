from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base


class SolicitudAdjunto(Base):
    __tablename__ = "solicitud_adjuntos"
    __table_args__ = (Index("idx_adjuntos_solicitud", "solicitud_id"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    solicitud_id: Mapped[UUID] = mapped_column(ForeignKey("solicitudes.id", ondelete="CASCADE"))
    nombre_archivo: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(100))
    tamanio_bytes: Mapped[int] = mapped_column(Integer)
    jira_attachment_id: Mapped[str | None] = mapped_column(String(50))
    url_descarga: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
