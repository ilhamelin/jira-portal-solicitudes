# SPEC-007: Webhooks Reactivos de Jira Cloud y Soporte de Archivos Adjuntos (Attachments)

- **Versión:** 1.0.0
- **Fase:** Funcionalidades Avanzadas de Integración (Event-Driven & Multi-Part)
- **Estado:** Listo para implementar
- **Responsable de Diseño:** Antigravity (Gemini)
- **Implementador:** Codex (GPT-6.1 Astra)

---

## 1. Objetivo y Contexto

Llevar la integración con Jira Cloud al máximo nivel técnico de la industria incorporando dos capacidades críticas para entornos empresariales:
1. **Arquitectura Reactiva basada en Eventos (Webhooks):**  
   Exponer un endpoint seguro en FastAPI (`POST /api/v1/webhooks/jira`) que reciba notificaciones en tiempo real desde Jira Cloud cuando un desarrollador actualice un ticket (`jira:issue_updated`), eliminando la necesidad de sincronizaciones manuales o polling continuo.
2. **Gestión de Archivos Adjuntos (Attachments):**  
   Permitir a los usuarios arrastrar y adjuntar archivos (capturas `.png`, `.jpg`, documentos `.pdf`, logs `.txt` de hasta 10 MB) al reportar incidentes, y transmitirlos automáticamente al ticket de Jira mediante la API REST v3 (`multipart/form-data`).

---

## 2. Archivos a Crear / Modificar

```text
backend/
├── app/
│   ├── core/
│   │   └── config.py                     (Modificar: agregar JIRA_WEBHOOK_SECRET)
│   ├── models/
│   │   ├── __init__.py
│   │   └── adjunto.py                    (Nuevo: Modelo SQLAlchemy SolicitudAdjunto)
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── adjunto.py                    (Nuevo: AdjuntoResponse)
│   │   └── webhook.py                    (Nuevo: JiraWebhookPayload)
│   ├── services/
│   │   └── jira_client.py                (Modificar: add upload_attachment, parse_webhook_event)
│   ├── api/v1/
│   │   ├── __init__.py
│   │   ├── webhooks.py                   (Nuevo: POST /api/v1/webhooks/jira)
│   │   └── solicitudes.py                (Modificar: POST /api/v1/solicitudes/{id}/adjuntos)
│   └── migrations/
│       └── 002_add_adjuntos_table.sql    (Nuevo: script SQL para tabla solicitud_adjuntos)
└── tests/
    └── test_webhooks_and_attachments.py  (Nuevo: pruebas de firma de webhook, payload y upload multipart)

frontend/
├── src/
│   ├── types/
│   │   └── index.ts                      (Extender con interfaz Adjunto)
│   ├── services/
│   │   └── api.ts                        (Agregar uploadAdjunto, getAdjuntos)
│   ├── components/
│   │   └── solicitudes/
│   │       ├── FileUploadZone.tsx        (Nuevo: Zona drag-and-drop con preview de imágenes)
│   │       └── AdjuntosList.tsx          (Nuevo: Lista de archivos con icono por tipo y tamaño)
│   └── pages/
│       ├── NuevaSolicitudPage.tsx        (Modificar: integrar FileUploadZone)
│       └── DetalleSolicitudPage.tsx      (Modificar: mostrar sección de adjuntos descargables)
```

---

## 3. Especificación de Persistencia y Contratos

### 3.1. Esquema SQL (`backend/migrations/002_add_adjuntos_table.sql`)
```sql
CREATE TABLE IF NOT EXISTS solicitud_adjuntos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    solicitud_id UUID NOT NULL REFERENCES solicitudes(id) ON DELETE CASCADE,
    nombre_archivo VARCHAR(255) NOT NULL,
    mime_type VARCHAR(100) NOT NULL,
    tamanio_bytes INT NOT NULL,
    jira_attachment_id VARCHAR(50) NULL,
    url_descarga TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_adjuntos_solicitud ON solicitud_adjuntos(solicitud_id);
```

### 3.2. Contrato de Adjuntos (`schemas/adjunto.py`)
```python
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel

class AdjuntoResponse(BaseModel):
    id: UUID
    solicitud_id: UUID
    nombre_archivo: str
    mime_type: str
    tamanio_bytes: int
    jira_attachment_id: str | None
    created_at: datetime
```

---

## 4. Algoritmos y Reglas de Negocio

### 4.1. Webhook Reactivo de Jira (`POST /api/v1/webhooks/jira`)
- **Seguridad:** El webhook debe validar el token secreto configurado en Jira mediante query parameter (`?token=...`) o cabecera personalizada `X-Webhook-Secret`.
- **Mapeo del Evento:**
  - Extrae `webhookEvent` (ej: `jira:issue_updated`).
  - Extrae `issue.key` (ej. `SOL-1`), `issue.fields.status.name` y `issue.fields.assignee.displayName`.
  - Busca en base de datos la solicitud vinculada a `jira_issue_key`.
  - Normaliza el estado mediante la función de mapeo (Backlog $\rightarrow$ Recibido, Done $\rightarrow$ Cerrado, etc.).
  - Actualiza `solicitudes` y `jira_integraciones` atómicamente.
  - Registra el intento en `intentos_integracion` con `operacion = 'SYNC_STATUS'`.
- Retorno: HTTP 200 `{"status": "processed", "issue_key": "SOL-1"}` en menos de 200 ms.

### 4.2. Envío de Adjuntos a Jira REST API v3
- Endpoint de Jira: `POST /rest/api/3/issue/{issueIdOrKey}/attachments`
- **Requerimiento específico de Jira API:** Debe incluir la cabecera `X-Atlassian-Token: no-check` para evitar el chequeo XSRF de Atlassian.
- Payload: `multipart/form-data` con el archivo binario y el nombre original.
- Respuesta Jira (HTTP 200): Lista de objetos con `id`, `filename`, `size`, `mimeType`.
- Persiste la información en `solicitud_adjuntos`.

### 4.3. Descarga Protegida de Adjuntos (`GET /api/v1/solicitudes/{id}/adjuntos/{adjunto_id}/download`)
- **Seguridad:** Requiere JWT. Aplica los mismos permisos de la solicitud (solicitante solo sus adjuntos, coordinador todos).
- **Mecanismo:** El cliente solicita la descarga a FastAPI; el backend consulta el contenido binario a Jira API (`GET /rest/api/3/attachment/content/{jira_attachment_id}`) usando las credenciales del servidor y transmite los bytes al navegador mediante `StreamingResponse` con las cabeceras `Content-Disposition: attachment; filename="{nombre_archivo}"`.
- **Ventaja:** Permite al usuario del portal descargar sus archivos sin necesidad de tener cuenta ni licencia paga en Jira/Atlassian.

---

## 5. Criterios de Aceptación (Verificables)

1. Enviar una petición POST simulada de webhook de Jira con firma válida actualiza el estado de la solicitud en Supabase y devuelve HTTP 200.
2. Peticiones de webhook con token inválido son rechazadas con HTTP 401 Unauthorized.
3. El frontend permite seleccionar o arrastrar un archivo (máximo 10 MB) durante la creación de la solicitud.
4. El archivo adjunto se envía exitosamente a Jira y queda visible tanto en el portal como en el ticket real en Atlassian Jira Cloud.
5. `pytest` incluye pruebas completas de validación de webhook y subida multipart.
