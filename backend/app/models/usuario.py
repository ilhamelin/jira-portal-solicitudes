from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, String, Uuid, func
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.database import Base

if TYPE_CHECKING:
    from .solicitud import Solicitud

ROL_USUARIO = ENUM("solicitante", "coordinador", name="rol_usuario", create_type=False)


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    rol: Mapped[str] = mapped_column(ROL_USUARIO, default="solicitante", server_default="solicitante")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    solicitudes: Mapped[list[Solicitud]] = relationship(back_populates="autor", lazy="raise", passive_deletes=True)
