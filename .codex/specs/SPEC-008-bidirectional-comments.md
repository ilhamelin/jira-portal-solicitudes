# SPEC-008: Comentarios Bidireccionales Sincronizados con Jira Cloud

- **Versión:** 1.0.0
- **Fase:** Funcionalidad Final de Colaboración
- **Estado:** Listo para implementar
- **Responsable de Diseño:** Antigravity (Gemini)
- **Implementador:** Codex (GPT-6.1 Astra)

---

## 1. Objetivo y Contexto

Permitir la comunicación fluida entre el usuario solicitante (en el portal web) y el equipo técnico de soporte (en Jira Cloud) mediante un muro de **comentarios bidireccionales** en la vista de detalle de cada solicitud:
1. Cuando un usuario escribe un comentario en el portal, se guarda en Supabase y se envía inmediatamente a Jira Cloud via REST API v3 en formato ADF (`POST /rest/api/3/issue/{key}/comment`).
2. Cuando el equipo técnico responde en Jira Cloud, el comentario se sincroniza hacia el portal (mostrando el badge *"Desde Jira"* con el nombre del técnico).

---

## 2. Archivos a Crear / Modificar

```text
backend/
├── app/
│   ├── models/
│   │   ├── __init__.py
│   │   └── comentario.py                 (Nuevo: Modelo SQLAlchemy SolicitudComentario)
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── comentario.py                 (Nuevo: ComentarioCreate, ComentarioResponse)
│   ├── services/
│   │   └── jira_client.py                (Modificar: add_issue_comment, get_issue_comments)
│   └── api/v1/
│       ├── __init__.py
│       └── solicitudes.py                (Modificar: GET y POST /api/v1/solicitudes/{id}/comentarios)
├── migrations/
│   └── 003_add_comentarios_table.sql     (Nuevo: DDL para tabla solicitud_comentarios)
└── tests/
    └── test_comentarios.py               (Nuevo: pruebas unitarias de creación, permisos y formato ADF)

frontend/
├── src/
│   ├── types/
│   │   └── index.ts                      (Extender: Comentario, ComentarioCreateInput)
│   ├── services/
│   │   └── api.ts                        (Agregar: getComentarios, crearComentario)
│   ├── components/
│   │   └── solicitudes/
│   │       └── ComentariosSection.tsx    (Nuevo: Timeline de comentarios con badges de origen y caja de texto)
│   └── pages/
│       └── DetalleSolicitudPage.tsx      (Modificar: integrar ComentariosSection debajo del stepper)
```

---

## 3. Especificación de Base de Datos y Contratos

### 3.1. Migración SQL (`backend/migrations/003_add_comentarios_table.sql`)
```sql
BEGIN;

CREATE TABLE IF NOT EXISTS solicitud_comentarios (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    solicitud_id UUID NOT NULL REFERENCES solicitudes(id) ON DELETE CASCADE,
    autor_id UUID NULL REFERENCES usuarios(id) ON DELETE SET NULL,
    autor_nombre VARCHAR(150) NOT NULL,
    origen VARCHAR(20) NOT NULL DEFAULT 'portal', -- 'portal' o 'jira'
    contenido TEXT NOT NULL,
    jira_comment_id VARCHAR(50) NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_comentarios_solicitud ON solicitud_comentarios(solicitud_id);

ALTER TABLE solicitud_comentarios ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON solicitud_comentarios FROM anon, authenticated;

COMMIT;
```

### 3.2. Contrato de Datos (`schemas/comentario.py` y `types/index.ts`)
```python
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field

class ComentarioCreate(BaseModel):
    contenido: str = Field(..., min_length=2, max_length=2000)

class ComentarioResponse(BaseModel):
    id: UUID
    solicitud_id: UUID
    autor_nombre: str
    origen: str  # "portal" | "jira"
    contenido: str
    jira_comment_id: str | None
    created_at: datetime
```

---

## 4. Algoritmos y Reglas de Negocio

### 4.1. Creación de Comentario (`POST /api/v1/solicitudes/{id}/comentarios`)
1. Validar que la solicitud existe y que el usuario autenticado tiene permisos (autor o coordinador).
2. Insertar en `solicitud_comentarios` con `origen = 'portal'`, `autor_id = current_user.id`, `autor_nombre = current_user.nombre`.
3. Si la solicitud está vinculada a Jira (`jira_issue_key` presente):
   - Construir payload ADF para Jira:
     ```json
     {
       "body": {
         "type": "doc",
         "version": 1,
         "content": [
           {
             "type": "paragraph",
             "content": [
               { "type": "text", "text": "[Portal - " + current_user.nombre + "]: " + contenido }
             ]
           }
         ]
       }
     }
     ```
   - Llamar a Jira: `POST /rest/api/3/issue/{key}/comment`.
   - Si la llamada a Jira es exitosa: guardar el `id` retornado de Jira en `jira_comment_id`.
   - Si la llamada a Jira falla (timeout o 5xx): **el comentario no se revierte**, se conserva en Supabase con `jira_comment_id = null` para que el usuario nunca pierda su texto, retornando HTTP 201 con el aviso de que quedó registrado localmente.
4. Retornar `ComentarioResponse` (HTTP 201).

### 4.2. Obtención y Sincronización de Comentarios (`GET /api/v1/solicitudes/{id}/comentarios`)
1. Consultar comentarios locales en `solicitud_comentarios` ordenados por `created_at ASC`.
2. Si la solicitud tiene `jira_issue_key`, consultar `GET /rest/api/3/issue/{key}/comment`:
   - Para cada comentario de Jira cuyo `id` no esté registrado en la BD local y que no provenga del portal (evitando duplicar comentarios propios):
     - Insertar en `solicitud_comentarios` con `origen = 'jira'`, `autor_nombre = comment.author.displayName`.
3. Devolver lista consolidada y ordenada cronológicamente.

---

## 5. Criterios de Aceptación (Verificables)

1. Publicar un comentario desde el portal lo hace visible inmediatamente en el ticket de Jira Cloud en Atlassian.
2. Comentar directamente en Jira Cloud hace que el comentario aparezca en el portal tras refrescar o consultar la solicitud.
3. Se distingue claramente el origen del comentario mediante badges visuales (*"Portal"* en verde esmeralda y *"Jira"* en azul Atlassian).
4. `pytest` valida creación de comentarios locales y el formateador ADF hacia Jira.
5. `npm run build` compila sin errores de tipos TypeScript.
