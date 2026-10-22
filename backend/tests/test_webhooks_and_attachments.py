from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from app.models import IntentoIntegracion, JiraIntegracion, Solicitud, SolicitudAdjunto

pytestmark = pytest.mark.asyncio
WEBHOOK = "/api/v1/webhooks/jira"
SECRET = {"X-Webhook-Secret": "test-only-webhook-secret"}


def webhook(state="Done", assignee="Ana Soporte", key="SOL-12"):
    return {"webhookEvent": "jira:issue_updated", "issue": {"key": key, "fields": {
        "status": {"name": state},
        "assignee": {"displayName": assignee} if assignee is not None else None,
    }}}


@pytest_asyncio.fixture
async def solicitud_id(session_factory, users):
    async with session_factory() as db:
        item = Solicitud(
            autor_id=users["solicitante"].id, titulo="Solicitud con archivos",
            descripcion="Descripción de prueba para adjuntos y eventos.", tipo="incidente",
            area="TI", prioridad_solicitada="media", estado_negocio="Recibido",
            updated_at=datetime.now(timezone.utc) - timedelta(days=7),
        )
        item.jira_integracion = JiraIntegracion(jira_issue_key="SOL-12", estado_integracion="sincronizado")
        db.add(item)
        await db.commit()
        return item.id


async def table_count(session_factory, model):
    async with session_factory() as db:
        return await db.scalar(select(func.count()).select_from(model))


@pytest.mark.parametrize("via", ["header", "query"])
async def test_valid_webhook_atomic_sync_and_minimal_audit(client, solicitud_id, session_factory, jira_mock, via):
    payload = webhook()
    payload["user"] = {"emailAddress": "private@example.test", "secret": "omit-me"}
    kwargs = {"headers": SECRET} if via == "header" else {"params": {"token": SECRET["X-Webhook-Secret"]}}
    response = await client.post(WEBHOOK, json=payload, **kwargs)
    assert response.status_code == 200
    assert response.json() == {"status": "processed", "issue_key": "SOL-12"}
    assert not jira_mock.requests
    async with session_factory() as db:
        item = await db.get(Solicitud, solicitud_id)
        link = await db.scalar(select(JiraIntegracion))
        attempt = await db.scalar(select(IntentoIntegracion))
        assert item.estado_negocio == "Cerrado" and item.responsable_jira == "Ana Soporte"
        assert item.closed_at is not None and link.ultima_sincronizacion_at is not None
        assert attempt.operacion == "SYNC_STATUS" and attempt.http_status == 200
        assert "user" not in attempt.payload_respuesta and "omit-me" not in str(attempt.payload_respuesta)


@pytest.mark.parametrize("headers,params", [({}, {}), ({"X-Webhook-Secret": "wrong"}, {}),
    ({}, {"token": "wrong"}), ({"X-Webhook-Secret": "wrong"}, {"token": SECRET["X-Webhook-Secret"]})])
async def test_invalid_webhook_secret(client, solicitud_id, session_factory, headers, params):
    response = await client.post(WEBHOOK, headers=headers, params=params, json=webhook())
    assert response.status_code == 401
    assert await table_count(session_factory, IntentoIntegracion) == 0


async def test_webhook_disabled_without_secret(client, application):
    application.state.settings.jira_webhook_secret = SecretStr("")
    assert (await client.post(WEBHOOK, headers=SECRET, json=webhook())).status_code == 401


@pytest.mark.parametrize("payload", [{}, [], {"webhookEvent": "jira:issue_updated"},
    {"webhookEvent": "jira:issue_updated", "issue": {"key": "SOL-12", "fields": {"status": {"name": "Done"}}}},
    webhook(key="../SOL-12"), webhook(assignee="x" * 151), webhook(state="Unmapped state")])
async def test_bad_webhook_is_422_without_changes(client, solicitud_id, session_factory, payload):
    response = await client.post(WEBHOOK, headers=SECRET, json=payload)
    assert response.status_code == 422
    async with session_factory() as db:
        assert (await db.get(Solicitud, solicitud_id)).estado_negocio == "Recibido"
    assert await table_count(session_factory, IntentoIntegracion) == 0


async def test_malformed_and_oversized_webhook(client):
    assert (await client.post(WEBHOOK, headers=SECRET, content=b"not-json")).status_code == 422
    assert (await client.post(WEBHOOK, headers=SECRET, content=b"x" * (1024 * 1024 + 1))).status_code == 413


async def test_ignored_events_and_unknown_ticket(client, session_factory):
    assert (await client.post(WEBHOOK, headers=SECRET, json={"webhookEvent": "comment_created"})).json() == {"status": "ignored"}
    assert (await client.post(WEBHOOK, headers=SECRET, json=webhook())).json() == {"status": "ignored", "issue_key": "SOL-12"}
    assert await table_count(session_factory, IntentoIntegracion) == 0


async def test_webhook_repeat_unassign_and_reopen(client, solicitud_id, session_factory):
    await client.post(WEBHOOK, headers=SECRET, json=webhook())
    async with session_factory() as db:
        item = await db.get(Solicitud, solicitud_id)
        closed_at, updated_at = item.closed_at, item.updated_at
    await client.post(WEBHOOK, headers=SECRET, json=webhook())
    async with session_factory() as db:
        item = await db.get(Solicitud, solicitud_id)
        assert (item.closed_at, item.updated_at) == (closed_at, updated_at)
    assert await table_count(session_factory, IntentoIntegracion) == 2
    response = await client.post(WEBHOOK, headers=SECRET, json=webhook("In Progress", None))
    assert response.status_code == 200
    async with session_factory() as db:
        item = await db.get(Solicitud, solicitud_id)
        assert item.closed_at is None and item.responsable_jira is None
        assert item.estado_negocio == "En desarrollo"


async def test_webhook_commit_failure_rolls_back_everything(client, solicitud_id, session_factory, monkeypatch):
    async def fail_commit(self):
        await self.flush()
        raise RuntimeError("Simulated commit failure")
    with monkeypatch.context() as patch:
        patch.setattr(AsyncSession, "commit", fail_commit)
        with pytest.raises(RuntimeError, match="Simulated commit failure"):
            await client.post(WEBHOOK, headers=SECRET, json=webhook())
    async with session_factory() as db:
        assert (await db.get(Solicitud, solicitud_id)).estado_negocio == "Recibido"
        assert (await db.scalar(select(JiraIntegracion))).ultima_sincronizacion_at is None
    assert await table_count(session_factory, IntentoIntegracion) == 0


def remote_attachment(name="log.txt", size=5, mime="text/plain"):
    return [{"id": "12345", "filename": name, "size": size, "mimeType": mime,
             "content": "https://untrusted.example.invalid/do-not-fetch"}]


@pytest.mark.parametrize("role", ["solicitante", "coordinador"])
@pytest.mark.parametrize("name,content,mime", [("log.txt", b"hello", "text/plain"),
    ("captura.png", b"\x89PNG\r\n\x1a\nexample", "image/png"),
    ("foto.jpg", b"\xff\xd8\xffexample", "image/jpeg"), ("manual.pdf", b"%PDF-1.7 example", "application/pdf")])
async def test_upload_multipart_and_list(client, solicitud_id, auth_headers, jira_mock, session_factory, role, name, content, mime):
    jira_mock.status, jira_mock.body = 200, remote_attachment(name, len(content), mime)
    response = await client.post(f"/api/v1/solicitudes/{solicitud_id}/adjuntos", headers=auth_headers(role), files={"file": (name, content, mime)})
    assert response.status_code == 201
    data = response.json()
    assert data["nombre_archivo"] == name and data["tamanio_bytes"] == len(content)
    assert data["mime_type"] == mime and data["jira_attachment_id"] == "12345"
    assert "url_descarga" not in data
    request = jira_mock.requests[0]
    assert request.url.path == "/rest/api/3/issue/SOL-12/attachments"
    assert request.headers["X-Atlassian-Token"] == "no-check"
    assert request.headers["Content-Type"].startswith("multipart/form-data; boundary=")
    assert b'name="file"' in request.content and content in request.content
    assert f'filename="{name}"'.encode() in request.content
    listing = await client.get(f"/api/v1/solicitudes/{solicitud_id}/adjuntos", headers=auth_headers(role))
    assert listing.json() == [data]
    async with session_factory() as db:
        item = await db.scalar(select(SolicitudAdjunto))
        assert item.url_descarga == "https://jira.example.test/rest/api/3/attachment/content/12345"


@pytest.mark.parametrize("role,status", [(None, 401), ("otro", 403)])
async def test_attachment_permissions_before_remote_call(client, solicitud_id, auth_headers, jira_mock, role, status):
    headers = auth_headers(role) if role else {}
    url = f"/api/v1/solicitudes/{solicitud_id}/adjuntos"
    assert (await client.post(url, headers=headers, files={"file": ("log.txt", b"hello", "text/plain")})).status_code == status
    assert (await client.get(url, headers=headers)).status_code == status
    assert (await client.get(f"{url}/{uuid4()}/descarga", headers=headers)).status_code == status
    assert not jira_mock.requests


async def test_attachment_missing_request_or_unsynced(client, solicitud_id, auth_headers, jira_mock, session_factory):
    headers = auth_headers()
    files = {"file": ("log.txt", b"hello", "text/plain")}
    assert (await client.post(f"/api/v1/solicitudes/{uuid4()}/adjuntos", headers=headers, files=files)).status_code == 404
    async with session_factory() as db:
        link = await db.scalar(select(JiraIntegracion))
        link.estado_integracion = "fallido"
        await db.commit()
    assert (await client.post(f"/api/v1/solicitudes/{solicitud_id}/adjuntos", headers=headers, files=files)).status_code == 409
    assert not jira_mock.requests


@pytest.mark.parametrize("name,content,mime,status", [
    ("script.html", b"html", "text/html", 415), ("log.txt", b"hello", "image/png", 415),
    ("log.txt", b"", "text/plain", 422), ("../log.txt", b"hello", "text/plain", 422),
    ("x" * 256 + ".txt", b"hello", "text/plain", 422),
    ("fake.png", b"not a png", "image/png", 415), ("fake.pdf", b"not pdf", "application/pdf", 415),
    ("fake.jpg", b"not jpeg", "image/jpeg", 415), ("binary.txt", b"\xff\xfe\x00", "text/plain", 415),
    ("huge.txt", b"x" * (10 * 1024 * 1024 + 1), "text/plain", 413),
], ids=["unsupported", "mime-mismatch", "empty", "path", "long-name", "fake-png", "fake-pdf", "fake-jpeg", "binary-text", "oversize"])
async def test_invalid_files_never_reach_jira(client, solicitud_id, auth_headers, jira_mock, session_factory, name, content, mime, status):
    response = await client.post(f"/api/v1/solicitudes/{solicitud_id}/adjuntos", headers=auth_headers(), files={"file": (name, content, mime)})
    assert response.status_code == status
    assert not jira_mock.requests
    assert await table_count(session_factory, SolicitudAdjunto) == 0


async def test_exact_file_limit(client, solicitud_id, auth_headers, jira_mock):
    content = b"x" * (10 * 1024 * 1024)
    jira_mock.status, jira_mock.body = 200, remote_attachment(size=len(content))
    response = await client.post(f"/api/v1/solicitudes/{solicitud_id}/adjuntos", headers=auth_headers(), files={"file": ("log.txt", content, "text/plain")})
    assert response.status_code == 201 and response.json()["tamanio_bytes"] == len(content)


@pytest.mark.parametrize("status,body", [(401, {}), (404, {}), (429, {}), (500, {}),
    (200, []), (200, [{}]), (200, remote_attachment(size=2)), (200, remote_attachment(name="other.txt"))])
async def test_jira_upload_error_does_not_persist_attachment(client, solicitud_id, auth_headers, jira_mock, session_factory, status, body):
    jira_mock.status, jira_mock.body = status, body
    response = await client.post(f"/api/v1/solicitudes/{solicitud_id}/adjuntos", headers=auth_headers(), files={"file": ("log.txt", b"hello", "text/plain")})
    assert response.status_code == 502
    assert len(jira_mock.requests) == 1
    assert await table_count(session_factory, SolicitudAdjunto) == 0


async def test_uncertain_upload_is_not_retried(client, solicitud_id, auth_headers, jira_mock, session_factory):
    jira_mock.error = httpx.ReadTimeout("test timeout")
    response = await client.post(f"/api/v1/solicitudes/{solicitud_id}/adjuntos", headers=auth_headers(), files={"file": ("log.txt", b"hello", "text/plain")})
    assert response.status_code == 502 and "confirmar" in response.json()["detail"]
    assert len(jira_mock.requests) == 1
    assert await table_count(session_factory, SolicitudAdjunto) == 0


async def test_upload_remote_success_with_local_commit_failure(
    client, solicitud_id, auth_headers, jira_mock, session_factory, monkeypatch,
):
    jira_mock.status, jira_mock.body = 200, remote_attachment()

    async def fail_commit(self):
        await self.flush()
        raise SQLAlchemyError("Simulated persistence failure")

    with monkeypatch.context() as patch:
        patch.setattr(AsyncSession, "commit", fail_commit)
        response = await client.post(
            f"/api/v1/solicitudes/{solicitud_id}/adjuntos", headers=auth_headers(),
            files={"file": ("log.txt", b"hello", "text/plain")},
        )
    assert response.status_code == 502 and "Jira recibió" in response.json()["detail"]
    assert len(jira_mock.requests) == 1
    assert await table_count(session_factory, SolicitudAdjunto) == 0


@pytest_asyncio.fixture
async def adjunto_id(session_factory, solicitud_id):
    async with session_factory() as db:
        item = SolicitudAdjunto(solicitud_id=solicitud_id, nombre_archivo="registro tést.txt",
            mime_type="text/plain", tamanio_bytes=5, jira_attachment_id="12345",
            url_descarga="https://untrusted.invalid/never-follow-this")
        db.add(item)
        await db.commit()
        return item.id


async def test_download_uses_fixed_jira_path_and_auth(client, solicitud_id, adjunto_id, auth_headers, jira_mock):
    jira_mock.status, jira_mock.text = 200, "hello"
    response = await client.get(f"/api/v1/solicitudes/{solicitud_id}/adjuntos/{adjunto_id}/descarga", headers=auth_headers())
    assert response.status_code == 200 and response.content == b"hello"
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "t%C3%A9st.txt" in response.headers["content-disposition"]
    request = jira_mock.requests[0]
    assert request.url.host == "jira.example.test"
    assert request.url.path == "/rest/api/3/attachment/content/12345"
    assert request.url.params["redirect"] == "false"
    assert request.headers["Authorization"].startswith("Basic ")


@pytest.mark.parametrize("status", [302, 401, 404, 500])
async def test_download_errors_do_not_redirect(client, solicitud_id, adjunto_id, auth_headers, jira_mock, status):
    jira_mock.status = status
    response = await client.get(f"/api/v1/solicitudes/{solicitud_id}/adjuntos/{adjunto_id}/descarga", headers=auth_headers())
    assert response.status_code == 502 and len(jira_mock.requests) == 1


async def test_download_wrong_attachment_and_cascade(client, solicitud_id, adjunto_id, auth_headers, jira_mock, session_factory):
    response = await client.get(f"/api/v1/solicitudes/{solicitud_id}/adjuntos/{uuid4()}/descarga", headers=auth_headers())
    assert response.status_code == 404 and not jira_mock.requests
    async with session_factory() as db:
        await db.delete(await db.get(Solicitud, solicitud_id))
        await db.commit()
    assert await table_count(session_factory, SolicitudAdjunto) == 0
