from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID
from pathlib import PurePath
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, File, UploadFile, Response
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload

from ...models import IntentoIntegracion, JiraIntegracion, Solicitud, Usuario, SolicitudAdjunto
from ...schemas.adjunto import AdjuntoResponse
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


MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024
ATTACHMENT_MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                   ".pdf": "application/pdf", ".txt": "text/plain"}


async def attachment_solicitud(solicitud_id: UUID, db, user: Usuario) -> Solicitud:
    item = await db.scalar(select(Solicitud).where(Solicitud.id == solicitud_id)
                           .options(selectinload(Solicitud.jira_integracion)))
    if item is None:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada.")
    if user.rol == "solicitante" and item.autor_id != user.id:
        raise HTTPException(status_code=403, detail="No puedes acceder a adjuntos de otros usuarios.")
    return item


@router.post("/{solicitud_id}/adjuntos", response_model=AdjuntoResponse, status_code=201)
async def upload_adjunto(
    solicitud_id: UUID, db: Database, user: PortalUser,
    jira: Annotated[JiraClient, Depends(get_jira_client)],
    file: Annotated[UploadFile, File()],
):
    try:
        item = await attachment_solicitud(solicitud_id, db, user)
        link = item.jira_integracion
        if link is None or not link.jira_issue_key or link.estado_integracion != "sincronizado":
            raise HTTPException(status_code=409, detail="La solicitud no tiene un ticket Jira sincronizado.")
        name = file.filename or ""
        if not name or len(name) > 255 or any(ord(char) < 32 or ord(char) == 127 for char in name) or "/" in name or "\\" in name:
            raise HTTPException(status_code=422, detail="Nombre de archivo inválido.")
        extension = PurePath(name).suffix.lower()
        mime = ATTACHMENT_MIME.get(extension)
        if mime is None or file.content_type != mime:
            raise HTTPException(status_code=415, detail="Solo se permiten PNG, JPEG, PDF y TXT con su MIME correspondiente.")
        content = await file.read(MAX_ATTACHMENT_SIZE + 1)
        if len(content) > MAX_ATTACHMENT_SIZE:
            raise HTTPException(status_code=413, detail="El archivo supera los 10 MB.")
        if not content:
            raise HTTPException(status_code=422, detail="El archivo está vacío.")
        valid = True
        if mime == "image/png":
            valid = content.startswith(b"\x89PNG\r\n\x1a\n")
        elif mime == "image/jpeg":
            valid = content.startswith(b"\xff\xd8\xff")
        elif mime == "application/pdf":
            valid = content.startswith(b"%PDF-")
        else:
            try:
                valid = "\x00" not in content.decode("utf-8")
            except UnicodeDecodeError:
                valid = False
        if not valid:
            raise HTTPException(status_code=415, detail="El contenido del archivo no corresponde a su formato.")
        try:
            remote = await jira.upload_attachment(link.jira_issue_key, name, content, mime)
        except JiraClientError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from None
        attachment = SolicitudAdjunto(
            solicitud_id=solicitud_id, nombre_archivo=name, mime_type=mime,
            tamanio_bytes=len(content), jira_attachment_id=remote.id,
            url_descarga=f"{str(jira.settings.jira_instance_url).rstrip('/')}/rest/api/3/attachment/content/{remote.id}",
        )
        db.add(attachment)
        try:
            await db.commit()
        except SQLAlchemyError:
            await db.rollback()
            raise HTTPException(
                status_code=502,
                detail="Jira recibió el archivo, pero no pudimos guardar su registro. Revisa el ticket antes de reenviarlo.",
            ) from None
        return attachment
    finally:
        await file.close()


@router.get("/{solicitud_id}/adjuntos", response_model=list[AdjuntoResponse])
async def get_adjuntos(solicitud_id: UUID, db: Database, user: PortalUser):
    await attachment_solicitud(solicitud_id, db, user)
    return list((await db.scalars(
        select(SolicitudAdjunto).where(SolicitudAdjunto.solicitud_id == solicitud_id)
        .order_by(SolicitudAdjunto.created_at, SolicitudAdjunto.id)
    )).all())


@router.get("/{solicitud_id}/adjuntos/{adjunto_id}/descarga")
async def download_adjunto(
    solicitud_id: UUID, adjunto_id: UUID, db: Database, user: PortalUser,
    jira: Annotated[JiraClient, Depends(get_jira_client)],
):
    await attachment_solicitud(solicitud_id, db, user)
    attachment = await db.scalar(select(SolicitudAdjunto).where(
        SolicitudAdjunto.id == adjunto_id, SolicitudAdjunto.solicitud_id == solicitud_id,
    ))
    if attachment is None or not attachment.jira_attachment_id:
        raise HTTPException(status_code=404, detail="Adjunto no encontrado.")
    try:
        content = await jira.download_attachment(attachment.jira_attachment_id)
    except JiraClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from None
    return Response(content, media_type=attachment.mime_type, headers={
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(attachment.nombre_archivo, safe='')}",
        "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff",
    })
