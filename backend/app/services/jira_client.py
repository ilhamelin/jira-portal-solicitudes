from base64 import b64encode
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from unicodedata import combining, normalize
from urllib.parse import quote
from uuid import UUID

import httpx
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import flag_modified

from ..core.config import Settings
from ..models import IntentoIntegracion, JiraIntegracion, Solicitud
from ..schemas.jira import BulkSyncResponse, JiraIssueResponse, JiraSyncResponse, SyncResultResponse

ISSUE_TYPES = {"incidente": "Error", "mejora": "Tarea"}
PRIORITIES = {"baja": "Lowest", "media": "Medium", "alta": "High", "urgente": "Highest"}
TERMINAL_STATES = {"Cerrado", "Rechazado"}
STATUS_ALIASES = {
    "Recibido": ("Backlog", "Por hacer", "To Do", "Recibido", "Abierto"),
    "En análisis": ("Seleccionado para desarrollo", "En análisis", "In Analysis", "Under Review"),
    "En desarrollo": ("En curso", "In Progress", "En desarrollo"),
    "En pruebas": ("En pruebas", "Testing", "QA", "En revisión"),
    "Cerrado": ("Listo", "Done", "Finalizado", "Cerrado", "Resuelto"),
    "Rechazado": ("Rechazado", "Descartado", "Won't Do", "Cancelado"),
}


def normalize_jira_status(name: str) -> str | None:
    def canonical(value: str) -> str:
        value = normalize("NFKD", value.strip().replace("’", "'"))
        return " ".join("".join(char for char in value if not combining(char)).casefold().split())
    value = canonical(name)
    return next((state for state, aliases in STATUS_ALIASES.items()
                 if value in {canonical(alias) for alias in aliases}), None)


class SyncNotAvailableError(Exception):
    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code


class JiraClientError(Exception):
    def __init__(self, message: str, http_status: int = 0, payload: Any = None):
        super().__init__(message)
        self.http_status = http_status
        self.payload = payload


@dataclass(frozen=True)
class JiraCreateResult:
    issue: JiraIssueResponse
    payload: Any


class JiraClient:
    def __init__(self, settings: Settings, *, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings
        token = settings.jira_api_token.get_secret_value()
        basic = b64encode(f"{settings.jira_user_email}:{token}".encode()).decode()
        self._secrets = (token, basic, settings.jwt_secret_key.get_secret_value(),
                         settings.database_url.get_secret_value())
        self._client = httpx.AsyncClient(
            base_url=str(settings.jira_instance_url).rstrip("/"),
            auth=httpx.BasicAuth(settings.jira_user_email, token),
            headers={"Accept": "application/json"},
            timeout=httpx.Timeout(10.0),
            transport=transport,
        )

    def sanitize(self, value: Any) -> Any:
        """Conservar el payload para auditoría sin persistir credenciales."""
        if isinstance(value, dict):
            return {
                key: "[REDACTED]" if any(
                    secret in key.lower() for secret in
                    ("authorization", "password", "token", "secret", "api_key", "database_url")
                ) else self.sanitize(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [self.sanitize(item) for item in value]
        if isinstance(value, str):
            for secret in self._secrets:
                if secret:
                    value = value.replace(secret, "[REDACTED]")
        return value

    def build_issue_payload(self, solicitud: Solicitud) -> dict:
        description = (
            f"Descripción: {solicitud.descripcion}\nÁrea: {solicitud.area}\n"
            f"Prioridad solicitada: {solicitud.prioridad_solicitada}\n\n"
            f"[CORRELATION_ID: {solicitud.id}]"
        )
        return {"fields": {
            "project": {"key": self.settings.jira_project_key},
            "summary": solicitud.titulo,
            "issuetype": {"name": ISSUE_TYPES[solicitud.tipo]},
            "priority": {"name": PRIORITIES[solicitud.prioridad_solicitada]},
            "description": {"type": "doc", "version": 1, "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": description}]},
            ]},
        }}

    async def create_issue(self, solicitud: Solicitud) -> JiraCreateResult:
        # Un único envío: no reintentar automáticamente un POST de resultado incierto.
        try:
            response = await self._client.post("/rest/api/3/issue", json=self.build_issue_payload(solicitud))
        except httpx.TimeoutException:
            raise JiraClientError("Jira agotó el tiempo de espera de 10 segundos.") from None
        except httpx.RequestError:
            raise JiraClientError("No se pudo establecer comunicación con Jira.") from None

        try:
            payload = self.sanitize(response.json())
        except ValueError:
            payload = {"body": self.sanitize(response.text)}
        if response.status_code != 201:
            raise JiraClientError(
                f"Jira devolvió HTTP {response.status_code}.", response.status_code, payload,
            )
        try:
            issue = JiraIssueResponse.model_validate(payload)
        except ValidationError:
            raise JiraClientError("Jira devolvió una respuesta de creación inválida.", 201, payload) from None
        return JiraCreateResult(issue=issue, payload=payload)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def get_issue_status(self, jira_issue_key: str) -> tuple[JiraSyncResponse, Any]:
        try:
            response = await self._client.get(
                f"/rest/api/3/issue/{quote(jira_issue_key, safe='')}",
                params={"fields": "status,assignee,priority"},
            )
        except httpx.TimeoutException:
            raise JiraClientError("Jira agotó el tiempo de espera de 10 segundos.") from None
        except httpx.RequestError:
            raise JiraClientError("No se pudo establecer comunicación con Jira.") from None
        try:
            payload = self.sanitize(response.json())
        except ValueError:
            payload = {"body": self.sanitize(response.text)}
        if response.status_code != 200:
            raise JiraClientError(f"Jira devolvió HTTP {response.status_code}.", response.status_code, payload)
        try:
            issue = JiraSyncResponse.model_validate(payload)
            status = issue.fields.get("status")
            assignee = issue.fields.get("assignee")
            if not isinstance(status, dict) or not isinstance(status.get("name"), str):
                raise ValueError
            if assignee is not None and (
                not isinstance(assignee, dict) or not isinstance(assignee.get("displayName"), str)
                or len(assignee["displayName"]) > 150
            ):
                raise ValueError
        except (ValidationError, ValueError):
            raise JiraClientError("Jira devolvió una respuesta de consulta inválida.", 200, payload) from None
        return issue, payload

    async def sync_solicitud(self, db: AsyncSession, solicitud_id: UUID) -> SyncResultResponse:
        solicitud = await db.scalar(
            select(Solicitud).where(Solicitud.id == solicitud_id)
            .options(selectinload(Solicitud.jira_integracion))
            .execution_options(populate_existing=True).with_for_update()
        )
        if solicitud is None:
            raise SyncNotAvailableError("Solicitud no encontrada.", 404)
        link = solicitud.jira_integracion
        if link is None or not link.jira_issue_key or link.estado_integracion != "sincronizado":
            raise SyncNotAvailableError("La solicitud no tiene un ticket Jira sincronizado.", 400)

        audit = IntentoIntegracion(solicitud_id=solicitud.id, operacion="SYNC_STATUS")
        try:
            issue, payload = await self.get_issue_status(link.jira_issue_key)
            new_state = normalize_jira_status(issue.fields["status"]["name"])
            if new_state is None:
                raise JiraClientError("El estado de Jira no tiene un mapeo configurado.", 200, payload)
        except JiraClientError as exc:
            audit.http_status = exc.http_status
            audit.error_mensaje = str(exc)
            audit.payload_respuesta = exc.payload
            db.add(audit)
            # Conservar estado de negocio, vínculo y fechas para permitir otro intento.
            await db.commit()
            raise

        assignee = issue.fields.get("assignee")
        new_assignee = assignee["displayName"] if assignee else None
        old_state = solicitud.estado_negocio
        previous_closed_at = solicitud.closed_at
        changed = old_state != new_state or solicitud.responsable_jira != new_assignee
        now = datetime.now(timezone.utc)
        if changed:
            solicitud.estado_negocio = new_state
            solicitud.responsable_jira = new_assignee
            solicitud.updated_at = now
        if new_state in TERMINAL_STATES:
            if old_state != new_state or solicitud.closed_at is None:
                solicitud.closed_at = now
        else:
            solicitud.closed_at = None
        if not changed and solicitud.closed_at != previous_closed_at:
            # Evitar que el onupdate del modelo adelante la fecha al reparar closed_at.
            flag_modified(solicitud, "updated_at")
        link.ultima_sincronizacion_at = now
        audit.http_status = 200
        audit.payload_respuesta = payload
        db.add(audit)
        await db.commit()
        return SyncResultResponse(
            solicitud_id=str(solicitud.id), jira_issue_key=link.jira_issue_key,
            estado_anterior=old_state, estado_nuevo=new_state,
            responsable_jira=new_assignee, hubo_cambios=changed,
        )

    async def sync_all_active_issues(self, db: AsyncSession) -> BulkSyncResponse:
        ids = list((await db.scalars(
            select(Solicitud.id).join(JiraIntegracion, JiraIntegracion.solicitud_id == Solicitud.id)
            .where(Solicitud.estado_negocio.not_in(TERMINAL_STATES),
                   JiraIntegracion.estado_integracion == "sincronizado",
                   JiraIntegracion.jira_issue_key.is_not(None),
                   JiraIntegracion.jira_issue_key != "")
            .order_by(Solicitud.id)
        )).all())
        details = []
        for solicitud_id in ids:
            try:
                details.append(await self.sync_solicitud(db, solicitud_id))
            except (JiraClientError, SyncNotAvailableError):
                # Los fallos remotos quedan auditados; un ticket no bloquea los demás.
                await db.rollback()
        return BulkSyncResponse(
            total_revisadas=len(ids), total_actualizadas=sum(item.hubo_cambios for item in details),
            detalles=details, timestamp=datetime.now(timezone.utc),
        )
