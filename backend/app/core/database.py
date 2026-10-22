from collections.abc import AsyncIterator
from uuid import uuid4

from fastapi import Request
from sqlalchemy import make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from .config import Settings


class Base(DeclarativeBase):
    pass


def build_engine(settings: Settings) -> AsyncEngine:
    try:
        url = make_url(settings.database_url.get_secret_value())
        if url.drivername not in {"postgres", "postgresql", "postgresql+asyncpg"}:
            raise ValueError
        if not url.host or not url.database or not url.username or url.port == 0:
            raise ValueError
    except (ArgumentError, ValueError, TypeError):
        raise ValueError("DATABASE_URL debe ser una URL válida de PostgreSQL.") from None

    connect_args = {
        "timeout": 15,
        "command_timeout": 30,
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
        "prepared_statement_name_func": lambda: f"__asyncpg_{uuid4().hex}__",
    }
    if "sslmode" in url.query:
        connect_args["ssl"] = url.query["sslmode"]
        url = url.difference_update_query(["sslmode"])
    return create_async_engine(
        url.set(drivername="postgresql+asyncpg"),
        poolclass=NullPool,
        connect_args=connect_args,
        hide_parameters=True,
    )


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
