import json
from base64 import b64encode
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import HTTPException
from jose import jwt
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role
from app.core.database import Base, build_engine, get_db
from app.core.security import create_access_token, get_password_hash, verify_password
from app.models import IntentoIntegracion, JiraIntegracion, Solicitud, Usuario

pytestmark = pytest.mark.asyncio
URL = "/api/v1/solicitudes"
PAYLOAD = {
    "titulo": "Error al abrir el portal", "descripcion": "El portal muestra un error al iniciar.",
    "tipo": "incidente", "area": "Operaciones", "prioridad_solicitada": "alta",
}


async def test_login_and_me(client, users, settings):
    response = await client.post("/api/v1/auth/login", json={
        "email": "solicitante@empresa.com", "password": "Solicitante123!",
    })
    assert response.status_code == 200
    body = response.json()
    assert body["rol"] == "solicitante" and body["user_id"] == str(users["solicitante"].id)
    assert body["token_type"] == "bearer"
    claims = jwt.decode(body["access_token"], settings.jwt_secret_key.get_secret_value(), algorithms=["HS256"])
    assert claims["exp"] - claims["iat"] == 8 * 3600
    assert claims["sub"] == str(users["solicitante"].id) and claims["rol"] == "solicitante"
    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json() == {"id": str(users["solicitante"].id), "email": "solicitante@empresa.com",
                         "nombre": "Solicitante Demo", "rol": "solicitante"}


async def test_coordinador_login(client, users):
    response = await client.post("/api/v1/auth/login", json={
        "email": "coordinador@empresa.com", "password": "Coordinador123!",
    })
    assert response.status_code == 200 and response.json()["rol"] == "coordinador"


@pytest.mark.parametrize("email,password", [
    ("solicitante@empresa.com", "incorrecta"), ("nadie@empresa.com", "incorrecta"),
    ("solicitante@empresa.com", "a" * 73),
])
async def test_bad_login(client, users, email, password):
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 401
    assert "access_token" not in response.json() and password not in response.text


@pytest.mark.parametrize("mode", ["missing", "garbage", "expired", "wrong-key", "wrong-alg", "no-exp", "unknown-user", "bad-sub"])
async def test_invalid_authentication(client, settings, users, mode):
    claims = {"sub": str(users["solicitante"].id), "exp": datetime.now(timezone.utc) + timedelta(hours=1)}
    key, algorithm = settings.jwt_secret_key.get_secret_value(), "HS256"
    if mode == "expired": claims["exp"] = datetime.now(timezone.utc) - timedelta(seconds=1)
    if mode == "wrong-key": key = "another-test-only-key"
    if mode == "wrong-alg": algorithm = "HS384"
    if mode == "no-exp": del claims["exp"]
    if mode == "unknown-user": claims["sub"] = str(uuid4())
    if mode == "bad-sub": claims["sub"] = "not-a-uuid"
    token = "not-a-token" if mode == "garbage" else jwt.encode(claims, key, algorithm=algorithm)
    headers = {} if mode == "missing" else {"Authorization": f"Bearer {token}"}
    response = await client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 401
    assert response.headers["www-authenticate"].lower() == "bearer"


@pytest.mark.parametrize("role", ["solicitante", "coordinador"])
async def test_successful_creation(client, session_factory, auth_headers, jira_mock, role):
    response = await client.post(URL, json=PAYLOAD, headers=auth_headers(role))
    assert response.status_code == 201
    body = response.json()
    assert body["estado_negocio"] == "Recibido"
    assert body["jira_integracion"]["estado_integracion"] == "sincronizado"
    assert body["jira_integracion"]["jira_issue_key"] == "SOL-12"
    assert body["jira_integracion"]["ultima_sincronizacion_at"] is not None
    async with session_factory() as db:
        assert await db.scalar(select(func.count()).select_from(Solicitud)) == 1
        audit = await db.scalar(select(IntentoIntegracion))
        link = await db.scalar(select(JiraIntegracion))
        assert audit.http_status == 201 and audit.error_mensaje is None
        assert audit.operacion == "CREATE_ISSUE" and audit.payload_respuesta == jira_mock.body
        assert link.solicitud_id == UUID(body["id"]) and link.jira_issue_id == "10001"
    assert len(jira_mock.requests) == 1


@pytest.mark.parametrize("tipo,jira_type", [("incidente", "Error"), ("mejora", "Tarea")])
@pytest.mark.parametrize("priority,jira_priority", [("baja", "Lowest"), ("media", "Medium"), ("alta", "High"), ("urgente", "Highest")])
async def test_jira_payload(client, auth_headers, jira_mock, settings, tipo, jira_type, priority, jira_priority):
    response = await client.post(URL, json={**PAYLOAD, "tipo": tipo, "prioridad_solicitada": priority}, headers=auth_headers())
    assert response.status_code == 201
    request = jira_mock.requests[0]
    assert request.method == "POST" and request.url.path == "/rest/api/3/issue"
    expected_auth = b64encode(f"{settings.jira_user_email}:{settings.jira_api_token.get_secret_value()}".encode()).decode()
    assert request.headers["authorization"] == f"Basic {expected_auth}"
    assert all(value == 10.0 for value in request.extensions["timeout"].values())
    fields = json.loads(request.content)["fields"]
    assert fields["project"] == {"key": "SOL"} and fields["summary"] == PAYLOAD["titulo"]
    assert fields["issuetype"] == {"name": jira_type} and fields["priority"] == {"name": jira_priority}
    adf = fields["description"]
    assert adf["type"] == "doc" and adf["version"] == 1
    assert adf["content"][0]["content"][0]["text"] == (
        f"Descripción: {PAYLOAD['descripcion']}\nÁrea: {PAYLOAD['area']}\n"
        f"Prioridad solicitada: {priority}\n\n[CORRELATION_ID: {response.json()['id']}]"
    )


async def test_local_records_are_committed_before_jira(client, auth_headers, jira_mock, session_factory):
    async def assert_committed(request):
        async with session_factory() as db:
            solicitud = await db.scalar(select(Solicitud))
            link = await db.scalar(select(JiraIntegracion))
            assert solicitud is not None and solicitud.estado_negocio == "Recibido"
            assert link.solicitud_id == solicitud.id and link.estado_integracion == "pendiente"
            assert await db.scalar(select(func.count()).select_from(IntentoIntegracion)) == 0
    jira_mock.before_response = assert_committed
    response = await client.post(URL, json=PAYLOAD, headers=auth_headers())
    assert response.status_code == 201


@pytest.mark.parametrize("status", [400, 401, 403, 404, 429, 500, 503])
async def test_jira_http_failure_preserves_solicitud(client, auth_headers, jira_mock, session_factory, status):
    jira_mock.status, jira_mock.body = status, {"errorMessages": ["Fallo simulado"]}
    response = await client.post(URL, json=PAYLOAD, headers=auth_headers())
    assert response.status_code == 201
    assert response.json()["jira_integracion"]["estado_integracion"] == "fallido"
    async with session_factory() as db:
        solicitud = await db.get(Solicitud, UUID(response.json()["id"]))
        audit = await db.scalar(select(IntentoIntegracion))
        link = await db.scalar(select(JiraIntegracion))
        assert solicitud is not None and solicitud.estado_negocio == "Recibido"
        assert link.jira_issue_key is None and link.ultima_sincronizacion_at is None
        assert audit.http_status == status and audit.error_mensaje
        assert audit.payload_respuesta == jira_mock.body
    assert len(jira_mock.requests) == 1


@pytest.mark.parametrize("error", [httpx.ReadTimeout, httpx.ConnectTimeout, httpx.ConnectError])
async def test_transport_failure_preserves_solicitud(client, auth_headers, jira_mock, session_factory, error):
    jira_mock.error = error("Sensitive transport error must not leak")
    response = await client.post(URL, json=PAYLOAD, headers=auth_headers())
    assert response.status_code == 201
    assert response.json()["jira_integracion"]["estado_integracion"] == "fallido"
    async with session_factory() as db:
        assert await db.get(Solicitud, UUID(response.json()["id"])) is not None
        audit = await db.scalar(select(IntentoIntegracion))
        assert audit.http_status == 0 and audit.error_mensaje
        assert "Sensitive" not in audit.error_mensaje
    assert len(jira_mock.requests) == 1


@pytest.mark.parametrize("status,body", [(201, {"unexpected": "body"}), (200, {"id": "1", "key": "SOL-1"})])
async def test_unexpected_jira_response_is_audited(client, auth_headers, jira_mock, session_factory, status, body):
    jira_mock.status, jira_mock.body = status, body
    response = await client.post(URL, json=PAYLOAD, headers=auth_headers())
    assert response.status_code == 201 and response.json()["jira_integracion"]["estado_integracion"] == "fallido"
    async with session_factory() as db:
        audit = await db.scalar(select(IntentoIntegracion))
        assert audit.http_status == status and audit.payload_respuesta == body


async def test_non_json_jira_error(client, auth_headers, jira_mock, session_factory):
    jira_mock.status, jira_mock.text = 502, "Upstream not available"
    response = await client.post(URL, json=PAYLOAD, headers=auth_headers())
    assert response.status_code == 201
    async with session_factory() as db:
        audit = await db.scalar(select(IntentoIntegracion))
        assert audit.http_status == 502 and audit.payload_respuesta == {"body": jira_mock.text}


async def test_error_payload_redacts_secrets(client, auth_headers, jira_mock, settings, session_factory):
    jira_mock.status = 401
    jira_mock.body = {"token": settings.jira_api_token.get_secret_value(), "nested": {
        "message": "failure: " + settings.jwt_secret_key.get_secret_value(),
        "Authorization": "Basic secret", "password": "do-not-store",
    }}
    response = await client.post(URL, json=PAYLOAD, headers=auth_headers())
    detail = await client.get(f"{URL}/{response.json()['id']}", headers=auth_headers())
    assert detail.status_code == 200
    async with session_factory() as db:
        stored = json.dumps((await db.scalar(select(IntentoIntegracion))).payload_respuesta)
    for secret in (settings.jira_api_token.get_secret_value(), settings.jwt_secret_key.get_secret_value(), "Basic secret", "do-not-store"):
        assert secret not in stored and secret not in detail.text
    assert "[REDACTED]" in stored


@pytest.mark.parametrize("change", [
    {"titulo": "a"}, {"titulo": "a" * 201}, {"descripcion": "corta"},
    {"area": "a"}, {"area": "a" * 101}, {"tipo": "otro"}, {"prioridad_solicitada": "otra"},
])
async def test_invalid_payload_has_no_side_effects(client, auth_headers, jira_mock, session_factory, change):
    response = await client.post(URL, json={**PAYLOAD, **change}, headers=auth_headers())
    assert response.status_code == 422 and not jira_mock.requests
    async with session_factory() as db:
        assert await db.scalar(select(func.count()).select_from(Solicitud)) == 0


async def test_default_priority_and_author_cannot_be_overridden(client, auth_headers, users, jira_mock, session_factory):
    payload = {key: value for key, value in PAYLOAD.items() if key != "prioridad_solicitada"}
    response = await client.post(URL, json={**payload, "autor_id": str(users["otro"].id)}, headers=auth_headers())
    assert response.status_code == 201 and response.json()["prioridad_solicitada"] == "media"
    async with session_factory() as db:
        solicitud = await db.get(Solicitud, UUID(response.json()["id"]))
        assert solicitud.autor_id == users["solicitante"].id


async def test_roles_list_and_detail(client, auth_headers, users):
    own = await client.post(URL, json=PAYLOAD, headers=auth_headers())
    other = await client.post(URL, json=PAYLOAD, headers=auth_headers("otro"))
    own_id, other_id = own.json()["id"], other.json()["id"]
    listed = await client.get(URL, headers=auth_headers())
    assert [item["id"] for item in listed.json()] == [own_id]
    all_items = await client.get(URL, headers=auth_headers("coordinador"))
    assert {item["id"] for item in all_items.json()} == {own_id, other_id}
    forbidden = await client.get(f"{URL}/{other_id}", headers=auth_headers())
    assert forbidden.status_code == 403 and "autor_email" not in forbidden.json()
    for role in ("otro", "coordinador"):
        detail = await client.get(f"{URL}/{other_id}", headers=auth_headers(role))
        assert detail.status_code == 200
        assert detail.json()["autor_email"] == users["otro"].email
        assert detail.json()["autor_nombre"] == users["otro"].nombre
        assert detail.json()["descripcion"] == PAYLOAD["descripcion"]
        assert detail.json()["intentos_recientes"][0]["http_status"] == 201


async def test_missing_and_invalid_id(client, auth_headers):
    assert (await client.get(f"{URL}/{uuid4()}", headers=auth_headers())).status_code == 404
    assert (await client.get(f"{URL}/not-a-uuid", headers=auth_headers())).status_code == 422


async def test_token_role_does_not_override_database_role(client, auth_headers, users, settings):
    other = await client.post(URL, json=PAYLOAD, headers=auth_headers("otro"))
    token = create_access_token(users["solicitante"].id, "coordinador", settings)
    headers = {"Authorization": f"Bearer {token}"}
    assert (await client.get(URL, headers=headers)).json() == []
    assert (await client.get(f"{URL}/{other.json()['id']}", headers=headers)).status_code == 403


async def test_pagination_and_empty_list(client, auth_headers):
    assert (await client.get(URL, headers=auth_headers())).json() == []
    await client.post(URL, json=PAYLOAD, headers=auth_headers())
    await client.post(URL, json=PAYLOAD, headers=auth_headers())
    first = (await client.get(f"{URL}?limit=1", headers=auth_headers())).json()
    second = (await client.get(f"{URL}?limit=1&offset=1", headers=auth_headers())).json()
    assert len(first) == len(second) == 1 and first[0]["id"] != second[0]["id"]
    assert (await client.get(f"{URL}?limit=0", headers=auth_headers())).status_code == 422


@pytest.mark.parametrize("method,path", [("POST", URL), ("GET", URL), ("GET", f"{URL}/{uuid4()}")])
async def test_routes_require_authentication(client, jira_mock, method, path):
    response = await client.request(method, path, json=PAYLOAD if method == "POST" else None)
    assert response.status_code == 401 and not jira_mock.requests


async def test_second_transaction_failure_preserves_initial_records(application, client, auth_headers, engine, session_factory, jira_mock):
    class FailingSecondCommit(AsyncSession):
        commits = 0
        async def commit(self):
            self.commits += 1
            if self.commits == 2:
                raise RuntimeError("simulated audit database failure")
            await super().commit()

    async def failing_db():
        async with FailingSecondCommit(engine, expire_on_commit=False) as db:
            try:
                yield db
            except Exception:
                await db.rollback()
                raise

    application.dependency_overrides[get_db] = failing_db
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=application, raise_app_exceptions=False), base_url="http://testserver") as failing_client:
            response = await failing_client.post(URL, json=PAYLOAD, headers=auth_headers())
        assert response.status_code == 500
    finally:
        application.dependency_overrides.pop(get_db)
    async with session_factory() as db:
        assert await db.scalar(select(func.count()).select_from(Solicitud)) == 1
        assert (await db.scalar(select(JiraIntegracion))).estado_integracion == "pendiente"
        assert await db.scalar(select(func.count()).select_from(IntentoIntegracion)) == 0
    assert len(jira_mock.requests) == 1


async def test_first_transaction_failure_never_calls_jira(application, client, auth_headers, engine, session_factory, jira_mock):
    class FailingCommit(AsyncSession):
        async def commit(self):
            raise RuntimeError("simulated database failure")

    async def failing_db():
        async with FailingCommit(engine, expire_on_commit=False) as db:
            yield db

    application.dependency_overrides[get_db] = failing_db
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=application, raise_app_exceptions=False), base_url="http://testserver") as failing_client:
            response = await failing_client.post(URL, json=PAYLOAD, headers=auth_headers())
        assert response.status_code == 500 and not jira_mock.requests
    finally:
        application.dependency_overrides.pop(get_db)
    async with session_factory() as db:
        assert await db.scalar(select(func.count()).select_from(Solicitud)) == 0


async def test_cors(client):
    response = await client.options(URL, headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    response = await client.options(URL, headers={"Origin": "https://untrusted.example", "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in response.headers


async def test_require_role_rejects_other_roles(users):
    check = require_role("coordinador")
    assert await check(users["coordinador"]) is users["coordinador"]
    with pytest.raises(HTTPException) as error:
        await check(users["solicitante"])
    assert error.value.status_code == 403


async def test_password_security():
    hashed = get_password_hash("Contraseña de prueba")
    assert hashed.startswith("$2b$") and verify_password("Contraseña de prueba", hashed)
    assert not verify_password("incorrecta", hashed)
    assert not verify_password("a" * 73, hashed)
    assert not verify_password("correcta", "invalid-hash")
    with pytest.raises(ValueError):
        get_password_hash("a" * 73)


async def test_models_match_existing_postgres_types():
    dialect = postgresql.dialect()
    assert set(Base.metadata.tables) == {"usuarios", "solicitudes", "jira_integraciones", "intentos_integracion"}
    assert Solicitud.__table__.c.tipo.type.name == "tipo_solicitud"
    assert Solicitud.__table__.c.estado_negocio.type.enums == ["Recibido", "En análisis", "En desarrollo", "En pruebas", "Cerrado", "Rechazado"]
    assert IntentoIntegracion.__table__.c.payload_respuesta.type.compile(dialect=dialect) == "JSONB"
    for model in (Usuario, Solicitud, JiraIntegracion, IntentoIntegracion):
        assert model.__table__.c.id.type.compile(dialect=dialect) == "UUID"
    assert next(iter(Solicitud.__table__.c.autor_id.foreign_keys)).ondelete == "RESTRICT"
    assert JiraIntegracion.__table__.c.solicitud_id.unique


@pytest.mark.parametrize("url", [
    "postgresql://user:p%40ss@localhost:5432/portal",
    "postgres://postgres.ref:p%40ss@pooler.example.test:6543/postgres",
    "postgresql+asyncpg://user:p%40ss@localhost:5432/portal?sslmode=require",
])
async def test_postgres_engine_configuration(settings, url):
    engine = build_engine(settings.model_copy(update={"database_url": SecretStr(url)}))
    try:
        assert engine.url.drivername == "postgresql+asyncpg"
        assert engine.url.password == "p@ss"
        assert "sslmode" not in engine.url.query
        assert engine.sync_engine.hide_parameters
    finally:
        await engine.dispose()


@pytest.mark.parametrize("url", ["invalid-secret-url", "sqlite:///secret.db", "postgresql://user:secret@localhost:invalid/db"])
async def test_invalid_database_url_is_not_exposed(settings, url):
    with pytest.raises(ValueError) as error:
        build_engine(settings.model_copy(update={"database_url": SecretStr(url)}))
    assert "secret" not in str(error.value)
