from datetime import datetime

from pydantic import BaseModel


class DashboardMetricsResponse(BaseModel):
    total_solicitudes: int
    tasa_resolucion_pct: float
    solicitudes_estancadas: int
    por_estado: dict[str, int]
    por_tipo: dict[str, int]
    por_prioridad: dict[str, int]
    por_area: dict[str, int]
    ultima_sincronizacion_general: datetime | None
