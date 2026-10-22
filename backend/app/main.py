"""Arranque: uvicorn app.main:app --app-dir backend. Pruebas: python -m pytest backend/tests."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from .api.v1 import auth, dashboard, jira, solicitudes, webhooks
from .core.config import Settings, get_settings
from .core.database import build_engine
from .services.jira_client import JiraClient


def create_app(settings: Settings | None = None, *, engine: AsyncEngine | None = None) -> FastAPI:
    settings = settings or get_settings()
    engine = engine if engine is not None else build_engine(settings)
    jira_client = JiraClient(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            yield
        finally:
            try:
                await jira_client.aclose()
            finally:
                await engine.dispose()

    application = FastAPI(title="Portal de Solicitudes", version="0.2.0", lifespan=lifespan)
    application.state.settings = settings
    application.state.engine = engine
    application.state.session_factory = async_sessionmaker(engine, expire_on_commit=False)
    application.state.jira_client = jira_client

    @application.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        # Liveness público: no depende de PostgreSQL ni de Jira.
        return {
            "status": "healthy",
            "service": "jira-portal-backend",
            "environment": settings.environment,
        }

    # Soporte para Chrome Private Network Access (PNA) desde Vercel hacia localhost
    @application.middleware("http")
    async def add_private_network_header(request, call_next):
        response = await call_next(request)
        if request.headers.get("access-control-request-private-network") == "true":
            response.headers["Access-Control-Allow-Private-Network"] = "true"
        return response

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=r"^https://.*\.vercel\.app$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Jira-Comments-Sync"],
    )
    application.include_router(auth.router, prefix="/api/v1")
    application.include_router(solicitudes.router, prefix="/api/v1")
    application.include_router(jira.router, prefix="/api/v1")
    application.include_router(dashboard.router, prefix="/api/v1")
    application.include_router(webhooks.router, prefix="/api/v1")
    return application


app = create_app()
