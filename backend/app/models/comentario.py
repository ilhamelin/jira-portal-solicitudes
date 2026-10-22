from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base


class SolicitudComentario(Base):
    __tablename__ = "solicitud_comentarios"
    __table_args__ = (
        Index("idx_comentarios_solicitud", "solicitud_id"),
        UniqueConstraint("solicitud_id", "jira_comment_id", name="uq_comentarios_jira"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    solicitud_id: Mapped[UUID] = mapped_column(ForeignKey("solicitudes.id", ondelete="CASCADE"))
    autor_id: Mapped[UUID | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    autor_nombre: Mapped[str] = mapped_column(String(150))
    origen: Mapped[str] = mapped_column(String(20), default="portal", server_default="portal")
    contenido: Mapped[str] = mapped_column(Text)
    jira_comment_id: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
