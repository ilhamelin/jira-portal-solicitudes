# Contexto del Proyecto: Portal de Solicitudes Integrado con Jira

## 1. Propósito y Stack
- **Objetivo:** Portal interno para reportar incidentes y mejoras, sincronizado con Jira Cloud y visualizado en un dashboard.
- **Frontend:** React 18+ / TypeScript / Vite / Tailwind CSS (Despliegue en **Vercel**).
- **Backend:** Python 3.11+ / FastAPI / HTTPX / Pydantic v2 / SQLAlchemy (async) / Supabase Client.
- **Base de Datos:** PostgreSQL en **Supabase** (usando pooler `6543` o direct connection).
- **Gestor de Tickets:** Jira Cloud REST API v3.

## 2. Flujo Híbrido (Antigravity + Codex)
- **Antigravity (Gemini Pro/Flash):** Diseña arquitectura, contratos de datos y escribe especificaciones quirúrgicas en `.codex/specs/SPEC-<num>-<nombre>.md`.
- **Codex (GPT-6.1 / Astra):** Lee la especificación correspondiente en `.codex/specs/` e implementa el código respetando estrictamente los contratos de tipos, rutas y criterios de aceptación sin desviarse del diseño.
- **Antigravity Verifier:** Ejecuta pruebas locales, linter y verificación de cumplimiento.

## 3. Convenciones Clave
- **Separación de Estados:**
  - *Estado de negocio:* `Recibido`, `En análisis`, `En desarrollo`, `En pruebas`, `Cerrado`, `Rechazado`.
  - *Estado de integración:* `pendiente`, `sincronizado`, `fallido`, `reintentando`.
- **Idempotencia:** Todo envío a Jira debe utilizar el UUID interno de la solicitud como clave de correlación para prevenir tickets duplicados ante caídas de red.
- **Secretos:** Nunca quemar credenciales en código; todas provienen de variables de entorno (`.env`).
