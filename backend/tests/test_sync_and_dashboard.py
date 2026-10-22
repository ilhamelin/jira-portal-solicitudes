from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import func, select

from app.models import IntentoIntegracion, JiraIntegracion, Solicitud
from app.services.dashboard_service import get_dashboard_metrics
from app.services.jira_client import STATUS_ALIASES, normalize_jira_status

pytestmark = pytest.mark.asyncio
SYNC_ALL = "/api/v1/jira/sync"
METRICS = "/api/v1/dashboard/metrics"


def issue_payload(state="En curso", assignee="Ana Soporte"):
    return {"id": "10001", "key": "SOL-12", "fields": {
        "status": {"name": state},
        "assignee": {"displayName": assignee} if assignee is not None else None,
        "priority": {"name": "High"},
    }}


@pytest_asyncio.fixture
async def make_solicitud(session_factory, users):
    async def create(*, state="Recibido", assignee=None, age_days=7, key="SOL-12",
                     integration_state="sincronizado", closed_at=None, updated_at=None,
                     kind="incidente", priority="media", final_priority=None, area="TI"):
        async with session_factory() as db:
            solicitud = Solicitud(
                autor_id=users["solicitante"].id, titulo="Solicitud de prueba para sincronizar",
                descripcion="Descripción de prueba para sincronización y métricas.",
                tipo=kind, area=area, prioridad_solicitada=priority,
                prioridad_definitiva=final_priority, estado_negocio=state,
                responsable_jira=assignee, closed_at=closed_at,
                updated_at=updated_at or datetime.now(timezone.utc) - timedelta(days=age_days),
            )
            db.add(solicitud)
            await db.flush()
            db.add(JiraIntegracion(solicitud_id=solicitud.id, jira_issue_key=key,
                                   estado_integracion=integration_state))
            await db.commit()
            return solicitud.id
    return create


@pytest.mark.parametrize("portal,jira_name", [(portal, alias) for portal, aliases in STATUS_ALIASES.items() for alias in aliases])
async def test_all_jira_status_aliases(portal, jira_name):
    assert normalize_jira_status(f"  {jira_name.upper()}  ") == portal


async def test_normalization_unknown_and_accents():
    assert normalize_jira_status("en analisis") == "En análisis"
    assert normalize_jira_status("Won’t Do") == "Rechazado"
    assert normalize_jira_status("Estado nuevo") is None
    assert normalize_jira_status("") is None


async def test_sync_updates_state_assignee_and_audits(client, auth_headers, make_solicitud, jira_mock, session_factory):
    solicitud_id = await make_solicitud()
    jira_mock.status, jira_mock.body = 200, issue_payload()
    response = await client.post(f"/api/v1/solicitudes/{solicitud_id}/sync", headers=auth_headers("coordinador"))
    assert response.status_code == 200
    assert response.json() == {"solicitud_id": str(solicitud_id), "jira_issue_key": "SOL-12",
                               "estado_anterior": "Recibido", "estado_nuevo": "En desarrollo",
                               "responsable_jira": "Ana Soporte", "hubo_cambios": True}
    request = jira_mock.requests[0]
    assert request.method == "GET" and request.url.path == "/rest/api/3/issue/SOL-12"
    assert request.url.params["fields"] == "status,assignee,priority"
    async with session_factory() as db:
        item = await db.get(Solicitud, solicitud_id)
        link = await db.scalar(select(JiraIntegracion))
        audit = await db.scalar(select(IntentoIntegracion))
        assert item.estado_negocio == "En desarrollo" and item.responsable_jira == "Ana Soporte"
        assert item.updated_at > datetime.now() - timedelta(minutes=1)
        assert item.closed_at is None and link.ultima_sincronizacion_at is not None
        assert audit.operacion == "SYNC_STATUS" and audit.http_status == 200
        assert audit.payload_respuesta == jira_mock.body and audit.error_mensaje is None


async def test_unchanged_sync_does_not_hide_stalled_ticket(client, auth_headers, make_solicitud, jira_mock, session_factory):
    solicitud_id = await make_solicitud(state="En desarrollo", assignee="Ana Soporte")
    async with session_factory() as db:
        before = (await db.get(Solicitud, solicitud_id)).updated_at
    jira_mock.status, jira_mock.body = 200, issue_payload()
    response = await client.post(f"/api/v1/solicitudes/{solicitud_id}/sync", headers=auth_headers("coordinador"))
    assert response.json()["hubo_cambios"] is False
    async with session_factory() as db:
        assert (await db.get(Solicitud, solicitud_id)).updated_at == before
        assert (await db.scalar(select(JiraIntegracion))).ultima_sincronizacion_at is not None
    metrics = (await client.get(METRICS, headers=auth_headers("coordinador"))).json()
    assert metrics["solicitudes_estancadas"] == 1


@pytest.mark.parametrize("state,expected", [("Done", "Cerrado"), ("Won't Do", "Rechazado")])
async def test_close_and_repeat_preserves_closure_date(client, auth_headers, make_solicitud, jira_mock, session_factory, state, expected):
    solicitud_id = await make_solicitud()
    jira_mock.status, jira_mock.body = 200, issue_payload(state)
    url = f"/api/v1/solicitudes/{solicitud_id}/sync"
    first = await client.post(url, headers=auth_headers("coordinador"))
    assert first.status_code == 200 and first.json()["estado_nuevo"] == expected
    async with session_factory() as db:
        original = await db.get(Solicitud, solicitud_id)
        closed_at, updated_at = original.closed_at, original.updated_at
        assert closed_at is not None
    second = await client.post(url, headers=auth_headers("coordinador"))
    assert second.json()["hubo_cambios"] is False
    async with session_factory() as db:
        item = await db.get(Solicitud, solicitud_id)
        assert item.closed_at == closed_at and item.updated_at == updated_at
        assert await db.scalar(select(func.count()).select_from(IntentoIntegracion)) == 2


async def test_reopening_clears_closed_at_and_removing_assignee(client, auth_headers, make_solicitud, jira_mock, session_factory):
    solicitud_id = await make_solicitud(state="Cerrado", closed_at=datetime.now(timezone.utc), assignee="Ana")
    jira_mock.status, jira_mock.body = 200, issue_payload("To Do", None)
    response = await client.post(f"/api/v1/solicitudes/{solicitud_id}/sync", headers=auth_headers("coordinador"))
    assert response.status_code == 200 and response.json()["hubo_cambios"]
    assert response.json()["responsable_jira"] is None
    async with session_factory() as db:
        item = await db.get(Solicitud, solicitud_id)
        assert item.closed_at is None and item.estado_negocio == "Recibido"


async def test_assignee_only_change_counts(client, auth_headers, make_solicitud, jira_mock):
    solicitud_id = await make_solicitud(state="En desarrollo", assignee="Anterior")
    jira_mock.status, jira_mock.body = 200, issue_payload()
    response = await client.post(f"/api/v1/solicitudes/{solicitud_id}/sync", headers=auth_headers("coordinador"))
    assert response.json()["estado_anterior"] == response.json()["estado_nuevo"]
    assert response.json()["hubo_cambios"] is True


@pytest.mark.parametrize("state,key", [("sincronizado", None), ("pendiente", "SOL-12"), ("fallido", "SOL-12"), ("reintentando", "SOL-12")])
async def test_unlinked_or_unsent_solicitud_returns_400(client, auth_headers, make_solicitud, jira_mock, state, key):
    solicitud_id = await make_solicitud(integration_state=state, key=key)
    response = await client.post(f"/api/v1/solicitudes/{solicitud_id}/sync", headers=auth_headers("coordinador"))
    assert response.status_code == 400 and not jira_mock.requests


async def test_missing_solicitud(client, auth_headers, jira_mock):
    response = await client.post(f"/api/v1/solicitudes/{uuid4()}/sync", headers=auth_headers("coordinador"))
    assert response.status_code == 404 and not jira_mock.requests


@pytest.mark.parametrize("status", [401, 404, 429, 500])
async def test_sync_remote_error_audited_without_corrupting_link(client, auth_headers, make_solicitud, jira_mock, session_factory, status):
    solicitud_id = await make_solicitud(assignee="Anterior")
    jira_mock.status, jira_mock.body = status, {"errorMessages": ["Error simulado"]}
    async with session_factory() as db:
        before = (await db.get(Solicitud, solicitud_id)).updated_at
    response = await client.post(f"/api/v1/solicitudes/{solicitud_id}/sync", headers=auth_headers("coordinador"))
    assert response.status_code == 502
    async with session_factory() as db:
        item = await db.get(Solicitud, solicitud_id)
        link = await db.scalar(select(JiraIntegracion))
        audit = await db.scalar(select(IntentoIntegracion))
        assert item.estado_negocio == "Recibido" and item.responsable_jira == "Anterior"
        assert item.updated_at == before
        assert link.estado_integracion == "sincronizado" and link.ultima_sincronizacion_at is None
        assert audit.operacion == "SYNC_STATUS" and audit.http_status == status and audit.error_mensaje


@pytest.mark.parametrize("mode", ["unknown", "timeout", "malformed", "invalid-assignee", "non-json"])
async def test_bad_sync_response_is_safe(client, auth_headers, make_solicitud, jira_mock, session_factory, mode):
    solicitud_id = await make_solicitud()
    jira_mock.status, jira_mock.body = 200, issue_payload("Unexpected workflow")
    if mode == "timeout": jira_mock.error = httpx.ReadTimeout("secret error should not leak")
    if mode == "malformed": jira_mock.body = {"unexpected": "response"}
    if mode == "invalid-assignee": jira_mock.body = issue_payload(assignee="a" * 151)
    if mode == "non-json": jira_mock.text = "<html>Proxy error</html>"
    response = await client.post(f"/api/v1/solicitudes/{solicitud_id}/sync", headers=auth_headers("coordinador"))
    assert response.status_code == 502 and "secret error" not in response.text
    async with session_factory() as db:
        item = await db.get(Solicitud, solicitud_id)
        audit = await db.scalar(select(IntentoIntegracion))
        assert item.estado_negocio == "Recibido" and item.closed_at is None
        assert audit.http_status == (0 if mode == "timeout" else 200)
        assert audit.error_mensaje and audit.operacion == "SYNC_STATUS"


@pytest.mark.parametrize("method,path", [("GET", METRICS), ("POST", SYNC_ALL), ("POST", f"/api/v1/solicitudes/{uuid4()}/sync")])
async def test_new_routes_require_coordinator(client, auth_headers, jira_mock, method, path):
    assert (await client.request(method, path)).status_code == 401
    assert (await client.request(method, path, headers=auth_headers())).status_code == 403
    assert not jira_mock.requests


async def test_bulk_only_syncs_active_linked_tickets(client, auth_headers, make_solicitud, jira_mock):
    changed = await make_solicitud()
    unchanged = await make_solicitud(state="En desarrollo", assignee="Ana Soporte")
    await make_solicitud(state="Cerrado")
    await make_solicitud(state="Rechazado")
    await make_solicitud(key=None)
    await make_solicitud(integration_state="fallido")
    jira_mock.status, jira_mock.body = 200, issue_payload()
    response = await client.post(SYNC_ALL, headers=auth_headers("coordinador"))
    assert response.status_code == 200
    body = response.json()
    assert body["total_revisadas"] == 2 and body["total_actualizadas"] == 1
    assert {item["solicitud_id"] for item in body["detalles"]} == {str(changed), str(unchanged)}
    assert len(jira_mock.requests) == 2 and body["timestamp"]


async def test_bulk_partial_failure_continues_and_audits(client, auth_headers, make_solicitud, jira_mock, session_factory):
    await make_solicitud()
    await make_solicitud()
    jira_mock.status, jira_mock.body = 200, issue_payload()
    async def fail_first(request):
        jira_mock.status = 429 if len(jira_mock.requests) == 1 else 200
    jira_mock.before_response = fail_first
    response = await client.post(SYNC_ALL, headers=auth_headers("coordinador"))
    assert response.status_code == 200
    assert response.json()["total_revisadas"] == 2 and response.json()["total_actualizadas"] == 1
    assert len(response.json()["detalles"]) == 1 and len(jira_mock.requests) == 2
    async with session_factory() as db:
        codes = list((await db.scalars(select(IntentoIntegracion.http_status))).all())
        assert sorted(codes) == [200, 429]


async def test_empty_bulk_and_dashboard(client, auth_headers, jira_mock):
    headers = auth_headers("coordinador")
    sync = await client.post(SYNC_ALL, headers=headers)
    assert sync.status_code == 200 and sync.json()["total_revisadas"] == 0
    assert sync.json()["total_actualizadas"] == 0 and sync.json()["detalles"] == []
    response = await client.get(METRICS, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total_solicitudes"] == 0 and body["tasa_resolucion_pct"] == 0.0
    assert body["solicitudes_estancadas"] == 0 and body["ultima_sincronizacion_general"] is None
    assert len(body["por_estado"]) == 6 and not any(body["por_estado"].values())
    assert body["por_tipo"] == {"incidente": 0, "mejora": 0} and body["por_area"] == {}
    assert not jira_mock.requests


async def test_dashboard_aggregations_and_effective_priority(client, auth_headers, make_solicitud, session_factory):
    await make_solicitud(state="Cerrado", kind="incidente", area="TI", priority="media", final_priority="urgente")
    await make_solicitud(state="Rechazado", kind="mejora", area="Ventas", priority="baja")
    await make_solicitud(state="En desarrollo", kind="mejora", area="TI", priority="alta")
    response = await client.get(METRICS, headers=auth_headers("coordinador"))
    assert response.status_code == 200
    body = response.json()
    assert body["total_solicitudes"] == 3 and body["tasa_resolucion_pct"] == 33.3
    assert body["solicitudes_estancadas"] == 1
    assert body["por_tipo"] == {"incidente": 1, "mejora": 2}
    assert body["por_area"] == {"TI": 2, "Ventas": 1}
    assert body["por_prioridad"] == {"baja": 1, "media": 0, "alta": 1, "urgente": 1}
    assert sum(body["por_estado"].values()) == body["total_solicitudes"]


async def test_stalled_exact_five_day_boundary(make_solicitud, session_factory):
    now = datetime(2026, 10, 21, 12, tzinfo=timezone.utc)
    await make_solicitud(updated_at=now - timedelta(days=5))
    await make_solicitud(updated_at=now - timedelta(days=5, seconds=1))
    await make_solicitud(updated_at=now - timedelta(days=4))
    await make_solicitud(state="Cerrado", updated_at=now - timedelta(days=8))
    await make_solicitud(state="Rechazado", updated_at=now - timedelta(days=8))
    async with session_factory() as db:
        result = await get_dashboard_metrics(db, now=now)
    assert result.total_solicitudes == 5 and result.solicitudes_estancadas == 1


async def test_dashboard_latest_sync_timestamp(client, auth_headers, make_solicitud, jira_mock, session_factory):
    solicitud_id = await make_solicitud()
    jira_mock.status, jira_mock.body = 200, issue_payload()
    await client.post(f"/api/v1/solicitudes/{solicitud_id}/sync", headers=auth_headers("coordinador"))
    response = await client.get(METRICS, headers=auth_headers("coordinador"))
    assert response.json()["ultima_sincronizacion_general"] is not None
    assert response.json()["solicitudes_estancadas"] == 0


async def test_sync_redacts_response_secrets(client, auth_headers, make_solicitud, jira_mock, session_factory, settings):
    solicitud_id = await make_solicitud()
    jira_mock.status, jira_mock.body = 200, issue_payload()
    jira_mock.body["debug"] = {"token": settings.jira_api_token.get_secret_value()}
    await client.post(f"/api/v1/solicitudes/{solicitud_id}/sync", headers=auth_headers("coordinador"))
    async with session_factory() as db:
        audit = await db.scalar(select(IntentoIntegracion))
        assert audit.payload_respuesta["debug"]["token"] == "[REDACTED]"


@pytest.mark.parametrize("state,closed_at,jira_state", [
    ("Cerrado", None, "Done"),
    ("En desarrollo", datetime(2026, 10, 1, tzinfo=timezone.utc), "In Progress"),
])
async def test_repair_closure_metadata_does_not_change_activity_timestamp(
    client, auth_headers, make_solicitud, jira_mock, session_factory, state, closed_at, jira_state,
):
    solicitud_id = await make_solicitud(state=state, closed_at=closed_at, assignee=None)
    async with session_factory() as db:
        previous_updated_at = (await db.get(Solicitud, solicitud_id)).updated_at
    jira_mock.status, jira_mock.body = 200, issue_payload(jira_state, None)
    response = await client.post(f"/api/v1/solicitudes/{solicitud_id}/sync", headers=auth_headers("coordinador"))
    assert response.status_code == 200 and response.json()["hubo_cambios"] is False
    async with session_factory() as db:
        item = await db.get(Solicitud, solicitud_id)
        assert item.updated_at == previous_updated_at
        assert (item.closed_at is not None) == (state == "Cerrado")
