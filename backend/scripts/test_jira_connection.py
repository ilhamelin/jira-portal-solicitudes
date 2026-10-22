"""Prueba de conexión con Jira Cloud REST API v3.

Ejecutar:
    python backend/scripts/test_jira_connection.py
"""

import base64
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import load_dotenv


def main() -> int:
    # Cargar .env de la raíz
    env_path = Path(__file__).resolve().parents[2] / ".env"
    load_dotenv(env_path, override=False)

    jira_url = os.getenv("JIRA_INSTANCE_URL", "").rstrip("/")
    jira_email = os.getenv("JIRA_USER_EMAIL", "").strip()
    jira_token = os.getenv("JIRA_API_TOKEN", "").strip()
    project_key = os.getenv("JIRA_PROJECT_KEY", "SOL").strip()

    if not all([jira_url, jira_email, jira_token]):
        print(
            "Error: Faltan variables en .env (JIRA_INSTANCE_URL, JIRA_USER_EMAIL, JIRA_API_TOKEN).",
            file=sys.stderr,
        )
        return 1

    # Preparar Basic Auth Header (base64 de email:token)
    credentials = f"{jira_email}:{jira_token}"
    encoded_credentials = base64.b64encode(credentials.encode("utf-8")).decode("ascii")
    headers = {
        "Authorization": f"Basic {encoded_credentials}",
        "Accept": "application/json",
        "User-Agent": "JiraPortalIntegration/1.0",
    }

    print(f"Probando conexión con Jira Cloud ({jira_url})...")

    # 1. Verificar identidad del usuario
    myself_url = f"{jira_url}/rest/api/3/myself"
    req_myself = urllib.request.Request(myself_url, headers=headers)
    try:
        with urllib.request.urlopen(req_myself, timeout=15) as resp:
            user_data = json.loads(resp.read().decode("utf-8"))
            display_name = user_data.get("displayName", "N/A")
            email = user_data.get("emailAddress", jira_email)
            print(f"  [OK] Autenticacion exitosa: {display_name} ({email})")
    except urllib.error.HTTPError as e:
        print(f"  [ERROR] Fallo de autenticacion HTTP {e.code}: {e.reason}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"  [ERROR] No se pudo conectar a Jira: {e}", file=sys.stderr)
        return 1

    # 2. Verificar existencia del proyecto SOL y sus tipos de incidencia
    project_url = f"{jira_url}/rest/api/3/project/{project_key}"
    req_project = urllib.request.Request(project_url, headers=headers)
    try:
        with urllib.request.urlopen(req_project, timeout=15) as resp:
            proj_data = json.loads(resp.read().decode("utf-8"))
            proj_name = proj_data.get("name", "N/A")
            issue_types = [it.get("name") for it in proj_data.get("issueTypes", [])]
            print(f"  [OK] Proyecto encontrado: '{proj_name}' (Key: {project_key})")
            print(f"  [INFO] Tipos de incidencia disponibles: {', '.join(issue_types)}")
            return 0
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(f"  [ERROR] Proyecto con clave '{project_key}' no fue encontrado en Jira.", file=sys.stderr)
        else:
            print(f"  [ERROR] HTTP {e.code} consultando proyecto: {e.reason}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"  [ERROR] Error al consultar proyecto Jira: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
