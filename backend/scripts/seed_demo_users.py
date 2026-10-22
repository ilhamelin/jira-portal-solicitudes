"""Carga demo: python backend/scripts/seed_demo_users.py.

Ejecutar después de 001_initial_schema.sql, únicamente sobre una base de demo
o desarrollo. Las cuentas usan las credenciales de prueba públicas de SPEC-001.
Repetir la carga conserva las cuentas existentes, sus roles y sus contraseñas.
"""

import asyncio
import sys

from passlib.context import CryptContext
from sqlalchemy import text

if __package__:
    from .test_db_connection import create_database_engine
else:
    from test_db_connection import create_database_engine


DEMO_USERS = (
    ("solicitante@empresa.com", "Solicitante Demo", "solicitante", "Solicitante123!"),
    ("coordinador@empresa.com", "Coordinador Demo", "coordinador", "Coordinador123!"),
)


async def main() -> int:
    try:
        engine = create_database_engine()
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    created = 0
    password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    statement = text(
        "INSERT INTO public.usuarios (email, nombre, rol, password_hash) "
        "VALUES (:email, :nombre, :rol, :password_hash) "
        "ON CONFLICT (email) DO NOTHING RETURNING id"
    )
    try:
        # Ambas inserciones se confirman juntas o se revierten juntas.
        async with engine.begin() as connection:
            for email, nombre, rol, password in DEMO_USERS:
                password_hash = await asyncio.to_thread(password_context.hash, password)
                result = await connection.execute(
                    statement,
                    {"email": email, "nombre": nombre, "rol": rol,
                     "password_hash": password_hash},
                )
                if result.scalar_one_or_none() is not None:
                    created += 1
        print(f"Carga demo completada: {created} creados; {len(DEMO_USERS) - created} existentes.")
        return 0
    except Exception:
        print(
            "No se completó la carga demo; la transacción se revirtió. "
            "Verifica la conexión, los permisos y que se haya aplicado "
            "001_initial_schema.sql.",
            file=sys.stderr,
        )
        return 1
    finally:
        await engine.dispose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
