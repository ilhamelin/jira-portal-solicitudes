from typing import Annotated

from fastapi import APIRouter, Depends

from ...models import Usuario
from ...schemas.dashboard import DashboardMetricsResponse
from ...services.dashboard_service import get_dashboard_metrics
from ..deps import Database, require_role

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/metrics", response_model=DashboardMetricsResponse)
async def metrics(db: Database, user: Annotated[Usuario, Depends(require_role("coordinador"))]):
    return await get_dashboard_metrics(db)
