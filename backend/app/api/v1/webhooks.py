from secrets import compare_digest
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError

from ...schemas.webhook import JiraWebhookPayload
from ...services.jira_client import JiraClient
from ..deps import Database, get_jira_client

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


async def verify_webhook_secret(request: Request) -> None:
    secret = request.app.state.settings.jira_webhook_secret.get_secret_value()
    # Una cabecera incorrecta no se puede compensar con un token distinto en la URL.
    query_secret = request.query_params.get("token", "")
    if "token" in request.query_params:
        # Uvicorn registra la URL al enviar la respuesta: redactar el scope ASGI.
        request.scope["query_string"] = urlencode([
            (key, "[REDACTED]" if key == "token" else value)
            for key, value in request.query_params.multi_items()
        ]).encode("ascii")
    provided = request.headers.get("X-Webhook-Secret")
    if provided is None:
        provided = query_secret
    if not secret or not compare_digest(provided.encode(), secret.encode()):
        raise HTTPException(status_code=401, detail="Token de webhook inválido.")


@router.post("/jira", dependencies=[Depends(verify_webhook_secret)])
async def jira_webhook(
    request: Request, db: Database,
    jira: Annotated[JiraClient, Depends(get_jira_client)],
):
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 1024 * 1024:
            raise HTTPException(status_code=413, detail="Evento demasiado grande.")
    try:
        payload = JiraWebhookPayload.model_validate_json(body)
        issue = jira.parse_webhook_event(payload)
    except (ValidationError, ValueError):
        # No reflejar el payload ni tokens en errores de validación.
        raise HTTPException(status_code=422, detail="Evento de Jira inválido o incompleto.") from None
    if issue is None:
        return {"status": "ignored"}
    try:
        processed = await jira.process_webhook(db, issue)
    except ValueError:
        raise HTTPException(status_code=422, detail="El estado de Jira no tiene un mapeo configurado.") from None
    return {"status": "processed" if processed else "ignored", "issue_key": issue.key}
