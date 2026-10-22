import json
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import JiraIntegracion, Solicitud, SolicitudComentario
from app.services.jira_client import PORTAL_COMMENT_PROPERTY

pytestmark = pytest.mark.asyncio


def adf(text):
    return {"type": "doc", "version": 1, "content": [
        {"type": "paragraph", "content": [{"type": "text", "text": text}]},
    ]}


def remote_comment(comment_id="10001", text="Respuesta del equipo técnico", **overrides):
    return {"id": comment_id, "body": adf(text), "author": {"displayName": "Ana Soporte"},
            "created": "2026-10-01T12:00:00.000+0000", **overrides}


def page(comments, offset=0, total=None):
    return {"startAt": offset, "maxResults": 100,
            "total": len(comments) if total is None else total, "comments": comments}


@pytest_asyncio.fixture
async def solicitud_id(session_factory, users):
    async with session_factory() as db:
        item = Solicitud(autor_id=users["solicitante"].id, titulo="Solicitud para comentarios",
            descripcion="Descripción de prueba para comentarios sincronizados.", tipo="incidente",
            area="TI", prioridad_solicitada="media", estado_negocio="Recibido",
            updated_at=datetime.now(timezone.utc) - timedelta(days=7))
        item.jira_integracion = JiraIntegracion(jira_issue_key="SOL-12", estado_integracion="sincronizado")
        db.add(item)
        await db.commit()
        return item.id


@pytest_asyncio.fixture
async def local_comment(session_factory, users, solicitud_id):
    async with session_factory() as db:
        item = SolicitudComentario(solicitud_id=solicitud_id, autor_id=users["solicitante"].id,
            autor_nombre="Solicitante Demo", origen="portal", contenido="Mensaje guardado localmente")
        db.add(item)
        await db.commit()
        return item.id


def url(solicitud_id):
    return f"/api/v1/solicitudes/{solicitud_id}/comentarios"


async def count_comments(session_factory):
    async with session_factory() as db:
        return await db.scalar(select(func.count()).select_from(SolicitudComentario))


@pytest.mark.parametrize("role", ["solicitante", "coordinador"])
async def test_post_persists_before_jira_and_sends_adf(client, solicitud_id, auth_headers, jira_mock, users, session_factory, role):
    async def assert_durable(request):
        assert await count_comments(session_factory) == 1
    jira_mock.before_response = assert_durable
    jira_mock.body = {"id": "7788"}
    response = await client.post(url(solicitud_id), headers=auth_headers(role), json={
        "contenido": "  Hola soporte\nNecesito más información.  ", "autor_nombre": "Suplantación",
    })
    assert response.status_code == 201
    data = response.json()
    assert data["contenido"] == "Hola soporte\nNecesito más información."
    assert data["origen"] == "portal" and data["autor_nombre"] == users[role].nombre
    assert data["jira_comment_id"] == "7788"
    assert response.headers["X-Jira-Comments-Sync"] == "ok"
    request = jira_mock.requests[0]
    assert request.method == "POST" and request.url.path == "/rest/api/3/issue/SOL-12/comment"
    payload = json.loads(request.content)
    assert payload["body"] == adf(f"[Portal - {users[role].nombre}]: Hola soporte\nNecesito más información.")
    assert payload["properties"] == [{"key": PORTAL_COMMENT_PROPERTY, "value": data["id"]}]
    async with session_factory() as db:
        row = await db.get(SolicitudComentario, UUID(data["id"]))
        assert row.autor_id == users[role].id
        assert (await db.get(Solicitud, solicitud_id)).updated_at < datetime.now() - timedelta(days=6)


@pytest.mark.parametrize("payload", [{}, {"contenido": "a"}, {"contenido": "   "},
    {"contenido": " a "}, {"contenido": "a" * 2001}, {"contenido": 123}])
async def test_post_validation(client, solicitud_id, auth_headers, jira_mock, session_factory, payload):
    response = await client.post(url(solicitud_id), headers=auth_headers(), json=payload)
    assert response.status_code == 422 and not jira_mock.requests
    assert await count_comments(session_factory) == 0


async def test_post_exact_length_limit(client, solicitud_id, auth_headers, jira_mock):
    jira_mock.body = {"id": "1"}
    assert (await client.post(url(solicitud_id), headers=auth_headers(), json={"contenido": "a" * 2000})).status_code == 201


@pytest.mark.parametrize("role,status", [(None, 401), ("otro", 403)])
async def test_comment_permissions(client, solicitud_id, auth_headers, jira_mock, role, status):
    headers = auth_headers(role) if role else {}
    assert (await client.get(url(solicitud_id), headers=headers)).status_code == status
    assert (await client.post(url(solicitud_id), headers=headers, json={"contenido": "No permitido"})).status_code == status
    assert not jira_mock.requests


async def test_missing_request(client, auth_headers, jira_mock):
    endpoint = url(uuid4())
    assert (await client.get(endpoint, headers=auth_headers())).status_code == 404
    assert (await client.post(endpoint, headers=auth_headers(), json={"contenido": "Comentario"})).status_code == 404
    assert not jira_mock.requests


async def test_no_ticket_local_post_and_get(client, solicitud_id, auth_headers, jira_mock, session_factory):
    async with session_factory() as db:
        await db.delete(await db.scalar(select(JiraIntegracion)))
        await db.commit()
    response = await client.post(url(solicitud_id), headers=auth_headers(), json={"contenido": "Comentario local"})
    assert response.status_code == 201 and response.json()["jira_comment_id"] is None
    assert response.headers["X-Jira-Comments-Sync"] == "not-linked"
    listing = await client.get(url(solicitud_id), headers=auth_headers())
    assert listing.json() == [response.json()] and not jira_mock.requests


@pytest.mark.parametrize("status,body", [(401, {}), (404, {}), (429, {}), (500, {}),
    (201, {}), (201, {"id": "bad"}), (201, []), (201, {"id": 123})])
async def test_post_jira_failure_keeps_local(client, solicitud_id, auth_headers, jira_mock, session_factory, status, body):
    jira_mock.status, jira_mock.body = status, body
    response = await client.post(url(solicitud_id), headers=auth_headers(), json={"contenido": "Conservar mi comentario"})
    assert response.status_code == 201 and response.json()["jira_comment_id"] is None
    assert response.headers["X-Jira-Comments-Sync"] == "failed"
    assert len(jira_mock.requests) == 1 and await count_comments(session_factory) == 1


async def test_post_timeout_is_not_retried(client, solicitud_id, auth_headers, jira_mock):
    jira_mock.error = httpx.ReadTimeout("test timeout")
    response = await client.post(url(solicitud_id), headers=auth_headers(), json={"contenido": "No repetir"})
    assert response.status_code == 201 and response.json()["jira_comment_id"] is None
    assert len(jira_mock.requests) == 1


async def test_failed_confirmation_commit_keeps_first_transaction(client, solicitud_id, auth_headers, jira_mock, session_factory, monkeypatch):
    jira_mock.body = {"id": "101"}
    original = AsyncSession.commit
    calls = 0
    async def commit(self):
        nonlocal calls
        calls += 1
        if calls == 2:
            await self.flush()
            raise SQLAlchemyError("Simulated confirmation failure")
        await original(self)
    with monkeypatch.context() as patch:
        patch.setattr(AsyncSession, "commit", commit)
        response = await client.post(url(solicitud_id), headers=auth_headers(), json={"contenido": "Registro durable"})
    assert response.status_code == 201 and response.json()["jira_comment_id"] is None
    assert await count_comments(session_factory) == 1
    async with session_factory() as db:
        assert (await db.scalar(select(SolicitudComentario))).jira_comment_id is None


@pytest.mark.parametrize("role", ["solicitante", "coordinador"])
async def test_get_imports_jira_chronologically_and_repeated_get_deduplicates(client, solicitud_id, local_comment, auth_headers, jira_mock, session_factory, role):
    jira_mock.status, jira_mock.body = 200, page([remote_comment("10"), remote_comment("11", "Otro comentario")])
    first = await client.get(url(solicitud_id), headers=auth_headers(role))
    second = await client.get(url(solicitud_id), headers=auth_headers(role))
    assert first.status_code == 200 and first.json() == second.json()
    assert [row["origen"] for row in first.json()] == ["jira", "jira", "portal"]
    assert first.json()[0]["autor_nombre"] == "Ana Soporte"
    assert first.json()[0]["created_at"].startswith("2026-10-01T12:00:00")
    assert await count_comments(session_factory) == 3
    assert jira_mock.requests[0].url.params["expand"] == "properties"


async def test_post_echo_and_uncertain_post_reconcile_by_uuid(client, solicitud_id, local_comment, auth_headers, jira_mock, session_factory):
    jira_mock.status, jira_mock.body = 200, page([remote_comment("101", "[Portal - Solicitante Demo]: Mensaje guardado localmente", properties=[
        {"key": PORTAL_COMMENT_PROPERTY, "value": str(local_comment)},
    ])])
    response = await client.get(url(solicitud_id), headers=auth_headers())
    assert len(response.json()) == 1 and response.json()[0]["origen"] == "portal"
    assert response.json()[0]["jira_comment_id"] == "101"
    assert response.json()[0]["contenido"] == "Mensaje guardado localmente"
    assert len(jira_mock.requests) == 1 and jira_mock.requests[0].method == "GET"


async def test_existing_remote_id_and_portal_property_do_not_echo(client, solicitud_id, local_comment, auth_headers, jira_mock, session_factory):
    async with session_factory() as db:
        row = await db.get(SolicitudComentario, local_comment)
        row.jira_comment_id = "1"
        await db.commit()
    jira_mock.status, jira_mock.body = 200, page([
        remote_comment("1"),
        remote_comment("2", properties=[{"key": PORTAL_COMMENT_PROPERTY, "value": str(uuid4())}]),
        remote_comment("3", "[Portal - Alguien]: Esto lo escribió un técnico sin propiedad"),
    ])
    response = await client.get(url(solicitud_id), headers=auth_headers())
    assert len(response.json()) == 2
    assert next(row for row in response.json() if row["jira_comment_id"] == "3")["origen"] == "jira"


async def test_restricted_and_internal_comments_are_not_imported(client, solicitud_id, auth_headers, jira_mock):
    jira_mock.status, jira_mock.body = 200, page([
        remote_comment("1", visibility={"type": "role", "value": "Developers"}),
        remote_comment("2", properties=[{"key": "sd.public.comment", "value": {"internal": True}}]),
    ])
    assert (await client.get(url(solicitud_id), headers=auth_headers())).json() == []


async def test_cached_jira_comment_becoming_restricted_is_removed(client, solicitud_id, auth_headers, jira_mock):
    jira_mock.status, jira_mock.body = 200, page([remote_comment("1")])
    assert len((await client.get(url(solicitud_id), headers=auth_headers())).json()) == 1
    jira_mock.body = page([remote_comment("1", visibility={"type": "group", "value": "private"})])
    assert (await client.get(url(solicitud_id), headers=auth_headers())).json() == []


@pytest.mark.parametrize("status,body", [(401, {}), (429, {}), (500, {}), (200, {}),
    (200, page([], total=2)), (200, page([remote_comment()], offset=10)),
    (200, page([remote_comment(body={"type": "invalid"})]))])
async def test_get_failure_returns_local_with_warning(client, solicitud_id, local_comment, auth_headers, jira_mock, status, body):
    jira_mock.status, jira_mock.body = status, body
    response = await client.get(url(solicitud_id), headers=auth_headers())
    assert response.status_code == 200 and len(response.json()) == 1
    assert response.json()[0]["id"] == str(local_comment)
    assert response.headers["X-Jira-Comments-Sync"] == "failed"


async def test_get_timeout_returns_local(client, solicitud_id, local_comment, auth_headers, jira_mock):
    jira_mock.error = httpx.ConnectError("test offline")
    response = await client.get(url(solicitud_id), headers=auth_headers())
    assert response.status_code == 200 and len(response.json()) == 1
    assert response.headers["X-Jira-Comments-Sync"] == "failed"


async def test_paginated_sync_does_not_truncate_or_duplicate(client, solicitud_id, auth_headers, jira_mock, session_factory):
    jira_mock.status = 200
    async def reply(request):
        offset = int(request.url.params["startAt"])
        jira_mock.body = page([remote_comment(str(offset + 1))], offset, 3)
    jira_mock.before_response = reply
    response = await client.get(url(solicitud_id), headers=auth_headers())
    assert len(response.json()) == 3 and len(jira_mock.requests) == 3
    assert await count_comments(session_factory) == 3


async def test_page_failure_imports_no_partial_history(client, solicitud_id, auth_headers, jira_mock, session_factory):
    jira_mock.status = 200
    async def reply(request):
        if request.url.params["startAt"] == "0":
            jira_mock.body = page([remote_comment()], 0, 2)
        else:
            jira_mock.status = 500
    jira_mock.before_response = reply
    response = await client.get(url(solicitud_id), headers=auth_headers())
    assert response.status_code == 200 and response.json() == []
    assert response.headers["X-Jira-Comments-Sync"] == "failed"
    assert await count_comments(session_factory) == 0


async def test_adf_flattening_preserves_lines_lists_mentions_and_plain_html(jira_mock):
    body = {"type": "doc", "version": 1, "content": [
        {"type": "paragraph", "content": [{"type": "text", "text": "Hola "},
            {"type": "mention", "attrs": {"text": "@Ana"}}, {"type": "hardBreak"},
            {"type": "text", "text": "<script>alert(1)</script>"}]},
        {"type": "bulletList", "content": [{"type": "listItem", "content": adf("Un punto")["content"]}]},
        {"type": "codeBlock", "content": [{"type": "text", "text": "print('ok')"}]},
    ]}
    assert jira_mock.client.comment_plain_text(body) == "Hola @Ana\n<script>alert(1)</script>\nUn punto\nprint('ok')"


async def test_unique_remote_id_and_delete_behavior(session_factory, users, solicitud_id, local_comment):
    async with session_factory() as db:
        row = await db.get(SolicitudComentario, local_comment)
        row.jira_comment_id = "1"
        await db.commit()
        db.add(SolicitudComentario(solicitud_id=solicitud_id, autor_nombre="Ana", origen="jira", contenido="Duplicado", jira_comment_id="1"))
        with pytest.raises(IntegrityError):
            await db.commit()
        await db.rollback()
        # Usuario sin solicitudes propias: comprobar SET NULL sobre el autor del comentario.
        row = await db.get(SolicitudComentario, local_comment)
        row.autor_id = users["coordinador"].id
        await db.commit()
        await db.delete(await db.get(type(users["coordinador"]), users["coordinador"].id))
        await db.commit()
        await db.refresh(row)
        assert row.autor_id is None and row.autor_nombre == "Solicitante Demo"
        await db.delete(await db.get(Solicitud, solicitud_id))
        await db.commit()
    assert await count_comments(session_factory) == 0


async def test_sync_warning_header_is_exposed_by_cors(client, solicitud_id, auth_headers, jira_mock):
    jira_mock.status = 500
    response = await client.get(url(solicitud_id), headers={**auth_headers(), "Origin": "http://localhost:5173"})
    assert "X-Jira-Comments-Sync" in response.headers["Access-Control-Expose-Headers"]
