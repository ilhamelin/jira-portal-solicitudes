"""Prueba End-to-End en Vivo: Crea una solicitud real en Supabase y en Jira Cloud.

Ejecutar:
    python backend/scripts/live_e2e_test.py
"""

import asyncio
import os
import sys
from pathlib import Path

from httpx import ASGITransport, AsyncClient

# Asegurar path de importación
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app


async def run_live_e2e() -> int:
    print("Iniciando prueba End-to-End en vivo (FastAPI + Supabase + Jira Cloud)...")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Login con usuario solicitante demo
        print("\n1. Autenticando con solicitante@empresa.com...")
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "solicitante@empresa.com", "password": "Solicitante123!"},
        )
        if login_resp.status_code != 200:
            print(f"Error en login: {login_resp.status_code} - {login_resp.text}")
            return 1

        token_data = login_resp.json()
        token = token_data["access_token"]
        print(f"  [OK] Login exitoso. Usuario: {token_data['nombre']} ({token_data['rol']})")

        headers = {"Authorization": f"Bearer {token}"}

        # 2. Crear solicitud real (Incidente)
        solicitud_payload = {
            "titulo": "Fallo crítico en generación de reportes contables PDF",
            "descripcion": "El módulo de contabilidad arroja timeout al exportar reportes mensuales consolidados. Afecta al cierre contable.",
            "tipo": "incidente",
            "area": "Finanzas",
            "prioridad_solicitada": "alta",
        }

        print("\n2. Enviando solicitud a /api/v1/solicitudes...")
        create_resp = await client.post(
            "/api/v1/solicitudes",
            json=solicitud_payload,
            headers=headers,
            timeout=20.0,
        )

        if create_resp.status_code != 201:
            print(f"Error creando solicitud: {create_resp.status_code} - {create_resp.text}")
            return 1

        solicitud = create_resp.json()
        print(f"  [OK] Solicitud creada en Supabase (ID: {solicitud['id']})")
        print(f"  [OK] Estado de Negocio: {solicitud['estado_negocio']}")

        jira_info = solicitud.get("jira_integracion")
        if jira_info and jira_info.get("jira_issue_key"):
            jira_key = jira_info["jira_issue_key"]
            estado_int = jira_info["estado_integracion"]
            print(f"\n=======================================================")
            print(f"  ¡TICKET CREADO EXITOSAMENTE EN JIRA CLOUD!")
            print(f"  Clave del Ticket: {jira_key}")
            print(f"  Estado Integración: {estado_int}")
            print(f"  URL en Jira: https://portal-solicitudes-dev.atlassian.net/browse/{jira_key}")
            print(f"=======================================================")
            return 0
        else:
            print(f"  [WARN] Ticket no sincronizado inmediatamente: {jira_info}")
            return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run_live_e2e()))
