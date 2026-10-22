"""Prueba de lectura: python backend/scripts/test_db_connection.py.

Lee DATABASE_URL del entorno o del .env de la raíz, sin sobrescribir el entorno.
Acepta postgresql://, postgres:// y postgresql+asyncpg://, con conexión directa
o vía pooler. No ejecuta migraciones ni modifica datos.
"""

import asyncio
import os
import sys
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from sqlalchemy import make_url, text
from sqlalchemy.exc import ArgumentError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool


def create_database_engine() -> AsyncEngine:
    """Configuración compartida por los dos scripts de SPEC-001."""
    load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise ValueError("Falta DATABASE_URL en el entorno o en el .env de la raíz.")

    try:
        url = make_url(database_url)
        if url.drivername not in {"postgres", "postgresql", "postgresql+asyncpg"}:
            raise ValueError
        # Acceder al puerto también valida que sea numérico.
        if not url.host or not url.database or not url.username or url.port == 0:
            raise ValueError
    except (ArgumentError, ValueError, TypeError) as exc:
        raise ValueError("DATABASE_URL debe ser una URL válida de PostgreSQL.") from exc

    connect_args = {
        "timeout": 15,
        "command_timeout": 30,
        # Evitar reutilizar sentencias preparadas entre sesiones del pooler.
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
        "prepared_statement_name_func": lambda: f"__asyncpg_{uuid4().hex}__",
    }
    # asyncpg recibe ssl, mientras que las URLs de libpq suelen usar sslmode.
    if "sslmode" in url.query:
        connect_args["ssl"] = url.query["sslmode"]
        url = url.difference_update_query(["sslmode"])

    return create_async_engine(
        url.set(drivername="postgresql+asyncpg"),
        poolclass=NullPool,
        connect_args=connect_args,
        hide_parameters=True,
    )


async def main() -> int:
    try:
        engine = create_database_engine()
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    try:
        async with engine.connect() as connection:
            version = (await connection.execute(text("SELECT version()"))).scalar_one()
        print(f"Conexión exitosa: {version}")
        return 0
    except Exception:
        # Las excepciones del driver pueden contener credenciales o la URL.
        print(
            "No se pudo consultar PostgreSQL. Verifica DATABASE_URL, SSL, "
            "conectividad y permisos.",
            file=sys.stderr,
        )
        return 1
    finally:
        await engine.dispose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
