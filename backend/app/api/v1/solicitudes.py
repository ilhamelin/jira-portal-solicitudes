from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ...models import IntentoIntegracion, JiraIntegracion, Solicitud, Usuario
from ...schemas.jira import SyncResultResponse
from ...schemas.solicitud import SolicitudCreate, SolicitudDetailResponse, SolicitudResponse
from ...services.jira_client import JiraClient, JiraClientError, SyncNotAvailableError
from ..deps import Database, PortalUser, get_jira_client, require_role

router = APIRouter(prefix="/solicitudes", tags=["solicitudes"])


@router.post("/{solicitud_id}/sync", response_model=SyncResultResponse)
async def sync_solicitud(
    solicitud_id: UUID, db: Database,
    user: Annotated[Usuario, Depends(require_role("coordinador"))],
    jira: Annotated[JiraClient, Depends(get_jira_client)],
):
    try:
        return await jira.sync_solicitud(db, solicitud_id)
    except SyncNotAvailableError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from None
    except JiraClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from None


@router.post("", response_model=SolicitudResponse, status_code=201)
async def create_solicitud(
    payload: SolicitudCreate, db: Database, user: PortalUser,
    jira: Annotated[JiraClient, Depends(get_jira_client)],
) -> SolicitudResponse:
    solicitud = Solicitud(autor_id=user.id, **payload.model_dump())
    integracion = JiraIntegracion(estado_integracion="pendiente")
    solicitud.jira_integracion = integracion
    db.add(solicitud)
    # Primera transacción durable antes de efectuar cualquier llamada externa.
    await db.commit()

    intento = IntentoIntegracion(solicitud_id=solicitud.id, operacion="CREATE_ISSUE")
    try:
        result = await jira.create_issue(solicitud)
    except JiraClientError as exc:
        integracion.estado_integracion = "fallido"
        intento.http_status = exc.http_status
        intento.error_mensaje = str(exc)
        intento.payload_respuesta = exc.payload
    else:
        integracion.jira_issue_id = result.issue.id
        integracion.jira_issue_key = result.issue.key
        integracion.estado_integracion = "sincronizado"
        integracion.ultima_sincronizacion_at = datetime.now(timezone.utc)
        intento.http_status = 201
        intento.payload_respuesta = result.payload
    db.add(intento)
    # Segunda transacción: resultado de integración y auditoría juntos.
    await db.commit()
    return SolicitudResponse.model_validate(solicitud)


@router.get("", response_model=list[SolicitudResponse])
async def list_solicitudes(
    db: Database, user: PortalUser,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[Solicitud]:
    statement = select(Solicitud).options(selectinload(Solicitud.jira_integracion))
    if user.rol == "solicitante":
        statement = statement.where(Solicitud.autor_id == user.id)
    statement = statement.order_by(Solicitud.created_at.desc(), Solicitud.id).offset(offset).limit(limit)
    return list((await db.scalars(statement)).all())


@router.get("/{solicitud_id}", response_model=SolicitudDetailResponse)
async def get_solicitud(solicitud_id: UUID, db: Database, user: PortalUser) -> SolicitudDetailResponse:
    solicitud = await db.scalar(
        select(Solicitud).where(Solicitud.id == solicitud_id)
        .options(selectinload(Solicitud.jira_integracion), selectinload(Solicitud.autor))
    )
    if solicitud is None:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada.")
    if user.rol == "solicitante" and solicitud.autor_id != user.id:
        raise HTTPException(status_code=403, detail="No puedes consultar solicitudes de otros usuarios.")
    intentos = (await db.scalars(
        select(IntentoIntegracion).where(IntentoIntegracion.solicitud_id == solicitud_id)
        .order_by(IntentoIntegracion.created_at.desc(), IntentoIntegracion.id.desc()).limit(10)
    )).all()
    return SolicitudDetailResponse(
        **SolicitudResponse.model_validate(solicitud).model_dump(),
        descripcion=solicitud.descripcion,
        autor_email=solicitud.autor.email,
        autor_nombre=solicitud.autor.nombre,
        intentos_recientes=[{
            "id": str(item.id), "operacion": item.operacion,
            "http_status": item.http_status, "error_mensaje": item.error_mensaje,
            "payload_respuesta": item.payload_respuesta, "created_at": item.created_at,
        } for item in intentos],
    )
