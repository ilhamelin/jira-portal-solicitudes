import json
import sys
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Permitir el mismo comando desde la raíz o desde backend/.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings, get_settings
from app.core.database import Base
from app.core.security import create_access_token, password_context
from app.models import Usuario
from app.services.jira_client import JiraClient


@pytest.fixture(autouse=True)
def isolate_environment(monkeypatch):
    # Las variables de prueba prevalecen sobre cualquier .env real del desarrollador.
    values = {
        "DATABASE_URL": "postgresql://test:test@127.0.0.1:1/unused",
        "JWT_SECRET_KEY": "test-only-jwt-key-with-at-least-32-characters",
        "JIRA_INSTANCE_URL": "https://jira.example.test",
        "JIRA_USER_EMAIL": "jira@empresa.com",
        "JIRA_API_TOKEN": "test-jira-token-never-use-in-production",
        "JIRA_PROJECT_KEY": "SOL",
        "ALLOWED_ORIGINS": "http://localhost:5173",
        "ENVIRONMENT": "test",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()

    async def forbidden_network(*args, **kwargs):
        raise AssertionError("Las pruebas no pueden efectuar llamadas HTTP reales.")

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", forbidden_network)
    yield
    get_settings.cache_clear()


@pytest.fixture
def settings(isolate_environment):
    return Settings(_env_file=None)


@pytest_asyncio.fixture
async def engine(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{(tmp_path / 'test.sqlite').as_posix()}")

    @event.listens_for(engine.sync_engine, "connect")
    def enable_foreign_keys(connection, _):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
def session_factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def users(session_factory):
    test_hasher = password_context.handler("bcrypt").using(rounds=4)
    password_hash = test_hasher.hash("Solicitante123!")
    users = {
        "solicitante": Usuario(email="solicitante@empresa.com", nombre="Solicitante Demo", rol="solicitante", password_hash=password_hash),
        "otro": Usuario(email="otro@empresa.com", nombre="Otra Persona", rol="solicitante", password_hash=password_hash),
        "coordinador": Usuario(email="coordinador@empresa.com", nombre="Coordinador Demo", rol="coordinador", password_hash=test_hasher.hash("Coordinador123!")),
    }
    async with session_factory() as session:
        session.add_all(users.values())
        await session.commit()
    return users


@pytest.fixture
def auth_headers(users, settings):
    def for_user(name="solicitante"):
        user = users[name]
        return {"Authorization": f"Bearer {create_access_token(user.id, user.rol, settings)}"}
    return for_user


@pytest_asyncio.fixture
async def jira_mock(settings):
    mock = SimpleNamespace(status=201, body={"id": "10001", "key": "SOL-12"},
                           text=None, error=None, requests=[], before_response=None)

    async def handle(request):
        mock.requests.append(request)
        # Registrar el JSON aquí también detecta payloads no serializables.
        if request.content:
            json.loads(request.content)
        if mock.before_response:
            await mock.before_response(request)
        if mock.error:
            raise mock.error
        if mock.text is not None:
            return httpx.Response(mock.status, text=mock.text)
        return httpx.Response(mock.status, json=mock.body)

    mock.client = JiraClient(settings, transport=httpx.MockTransport(handle))
    try:
        yield mock
    finally:
        await mock.client.aclose()


@pytest_asyncio.fixture
async def application(settings, engine, jira_mock):
    # Importar después de instalar las variables aisladas de prueba.
    from app.api.deps import get_jira_client
    from app.main import create_app

    application = create_app(settings, engine=engine)

    async def mock_jira():
        return jira_mock.client

    application.dependency_overrides[get_jira_client] = mock_jira
    async with application.router.lifespan_context(application):
        yield application
    application.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client(application):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application), base_url="http://testserver",
    ) as client:
        yield client
