from datetime import datetime, timedelta

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import JiraIntegracion, Solicitud
from ..models.solicitud import ESTADO_NEGOCIO, PRIORIDAD, TIPO_SOLICITUD
from ..schemas.dashboard import DashboardMetricsResponse
from .jira_client import TERMINAL_STATES


async def get_dashboard_metrics(db: AsyncSession, *, now: datetime | None = None) -> DashboardMetricsResponse:
    # Usar el reloj de PostgreSQL en producción y una referencia fija en pruebas de frontera.
    if now is None:
        now = await db.scalar(select(func.now()))
    cutoff = now - timedelta(days=5)
    priority = func.coalesce(Solicitud.prioridad_definitiva, Solicitud.prioridad_solicitada)
    stalled = Solicitud.estado_negocio.not_in(TERMINAL_STATES) & (Solicitud.updated_at < cutoff)
    rows = (await db.execute(
        select(Solicitud.estado_negocio, Solicitud.tipo, priority, Solicitud.area,
               func.count(), func.sum(case((stalled, 1), else_=0)))
        .group_by(Solicitud.estado_negocio, Solicitud.tipo, priority, Solicitud.area)
    )).all()
    states = dict.fromkeys(ESTADO_NEGOCIO.enums, 0)
    types = dict.fromkeys(TIPO_SOLICITUD.enums, 0)
    priorities = dict.fromkeys(PRIORIDAD.enums, 0)
    areas: dict[str, int] = {}
    total = total_stalled = 0
    for state, kind, level, area, count, stalled_count in rows:
        states[state] += count
        types[kind] += count
        priorities[level] += count
        areas[area] = areas.get(area, 0) + count
        total += count
        total_stalled += stalled_count
    last_sync = await db.scalar(select(func.max(JiraIntegracion.ultima_sincronizacion_at)))
    return DashboardMetricsResponse(
        total_solicitudes=total,
        tasa_resolucion_pct=round(states["Cerrado"] / total * 100, 1) if total else 0.0,
        solicitudes_estancadas=total_stalled,
        por_estado=states, por_tipo=types, por_prioridad=priorities, por_area=areas,
        ultima_sincronizacion_general=last_sync,
    )
