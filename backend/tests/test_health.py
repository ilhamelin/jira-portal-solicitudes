import pytest

from app.core.database import get_db


@pytest.mark.asyncio
@pytest.mark.parametrize("environment", ["test", "production"])
async def test_public_health_without_database_or_jira(
    client, application, jira_mock, monkeypatch, environment
):
    monkeypatch.setattr(application.state.settings, "environment", environment)

    async def forbidden_db():
        raise AssertionError("El health check no debe consultar la base de datos.")
        yield

    application.dependency_overrides[get_db] = forbidden_db
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "service": "jira-portal-backend",
        "environment": environment,
    }
    assert not jira_mock.requests
    assert "DATABASE_URL" not in response.text and "JWT_SECRET_KEY" not in response.text
