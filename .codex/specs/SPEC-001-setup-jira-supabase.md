# SPEC-001: Arquitectura Base, Esquema de Supabase y Configuración de Jira Cloud

- **Versión:** 1.0.0
- **Fase:** Etapa 1 (Configuración de Jira Cloud y Supabase)
- **Estado:** Listo para implementar
- **Responsable de Diseño:** Antigravity (Gemini)
- **Implementador:** Codex (GPT-6.1 Astra)

---

## 1. Resoluciones de Arquitectura y Decisiones Técnicas

A partir de las cuestiones planteadas en `AGENTS.md`, se fijan formalmente las siguientes decisiones:

| Tema | Decisión Aprobada | Justificación |
| :--- | :--- | :--- |
| **Alcance de Supabase** | **Exclusivamente Base de Datos PostgreSQL Gestionada**. | Todo acceso a datos pasa por FastAPI mediante SQLAlchemy asíncrono (`asyncpg`) conectado al Transaction Pooler (puerto `6543`). El frontend **no** se comunica directamente con Supabase. |
| **Autenticación** | **JWT propio gestionado en FastAPI** (`passlib[bcrypt]` + `python-jose`). | Demuestra control completo de seguridad en el backend (OAuth2PasswordBearer, roles y hashing). No acopla el portal a un SDK propietario y permite ejecutar el proyecto 100% offline con Docker Compose. |
| **Hosting del Backend** | **Render / Docker** en producción, Docker Compose en local. | Soporta ejecución continua para workers y elimina los límites de tiempo agresivos de Vercel Serverless para peticiones a Jira. |
| **Idempotencia con Jira** | Inyección de UUID en descripción y búsqueda preventiva por JQL. | Al crear un ticket en Jira, se incluye la marca `[CORRELATION_ID: <uuid>]` en la descripción. En caso de reintento tras timeout, el backend ejecuta primero `JQL: project = "SOL" AND text ~ "<uuid>"` para evitar duplicación. |
| **Métricas Temporales** | Incorporación de `created_at`, `updated_at`, `closed_at`. | Solicitudes "estancadas" se definen formalmente como tickets activos (`estado_negocio` != `Cerrado` y != `Rechazado`) con `updated_at < NOW() - INTERVAL '5 days'`. |

---

## 2. Configuración de Jira Cloud (Manual - Usuario)

El usuario debe configurar en su instancia `https://<org>.atlassian.net`:

1. **Proyecto:**
   - Tipo: **Gestionado por la empresa (Company-managed)**.
   - Plantilla: **Kanban**.
   - Nombre: `Portal de Solicitudes` | Clave (Key): `SOL`.
2. **Tipos de Incidencia (Issue Types):**
   - `Incidente` (Defectos operativos, fallas de sistema).
   - `Mejora` (Solicitudes de cambio, optimizaciones).
3. **Flujo de Trabajo (Workflow) y Estados:**
   - `Recibido` (Estado inicial al crear).
   - `En análisis` (Transición desde `Recibido`).
   - `En desarrollo` (Transición desde `En análisis` o devuelto desde `En pruebas`).
   - `En pruebas` (Transición desde `En desarrollo`).
   - `Cerrado` (Transición terminal con resolución `Listo` o `Completado`).
   - `Rechazado` (Transición desde `En análisis` con resolución `Rechazado` o `No aplica`).

---

## 3. Modelo de Persistencia (Esquema SQL para Supabase / PostgreSQL)

Archivo objetivo: `backend/migrations/001_initial_schema.sql`

```sql
-- Extensiones necesarias
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Tabla de Usuarios
CREATE TYPE rol_usuario AS ENUM ('solicitante', 'coordinador');

CREATE TABLE usuarios (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    nombre VARCHAR(150) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    rol rol_usuario NOT NULL DEFAULT 'solicitante',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. Tabla de Solicitudes
CREATE TYPE tipo_solicitud AS ENUM ('incidente', 'mejora');
CREATE TYPE prioridad_tipo AS ENUM ('baja', 'media', 'alta', 'urgente');
CREATE TYPE estado_negocio_tipo AS ENUM (
    'Recibido', 
    'En análisis', 
    'En desarrollo', 
    'En pruebas', 
    'Cerrado', 
    'Rechazado'
);

CREATE TABLE solicitudes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    autor_id UUID NOT NULL REFERENCES usuarios(id) ON DELETE RESTRICT,
    titulo VARCHAR(200) NOT NULL,
    descripcion TEXT NOT NULL,
    tipo tipo_solicitud NOT NULL,
    area VARCHAR(100) NOT NULL,
    prioridad_solicitada prioridad_tipo NOT NULL DEFAULT 'media',
    prioridad_definitiva prioridad_tipo NULL,
    estado_negocio estado_negocio_tipo NOT NULL DEFAULT 'Recibido',
    responsable_jira VARCHAR(150) NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    closed_at TIMESTAMPTZ NULL
);

-- 3. Tabla de Vínculo con Jira
CREATE TYPE estado_integracion_tipo AS ENUM ('pendiente', 'sincronizado', 'fallido', 'reintentando');

CREATE TABLE jira_integraciones (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    solicitud_id UUID UNIQUE NOT NULL REFERENCES solicitudes(id) ON DELETE CASCADE,
    jira_issue_id VARCHAR(50) NULL,
    jira_issue_key VARCHAR(50) NULL, -- ej: SOL-101
    estado_integracion estado_integracion_tipo NOT NULL DEFAULT 'pendiente',
    ultima_sincronizacion_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 4. Tabla de Auditoría e Intentos de Integración
CREATE TYPE operacion_integracion_tipo AS ENUM ('CREATE_ISSUE', 'SYNC_STATUS', 'UPDATE_PRIORITY');

CREATE TABLE intentos_integracion (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    solicitud_id UUID NOT NULL REFERENCES solicitudes(id) ON DELETE CASCADE,
    operacion operacion_integracion_tipo NOT NULL,
    http_status INT NULL,
    error_mensaje TEXT NULL,
    payload_respuesta JSONB NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Índices de consulta rápida
CREATE INDEX idx_solicitudes_autor ON solicitudes(autor_id);
CREATE INDEX idx_solicitudes_estado ON solicitudes(estado_negocio);
CREATE INDEX idx_jira_integraciones_key ON jira_integraciones(jira_issue_key);
CREATE INDEX idx_jira_integraciones_estado ON jira_integraciones(estado_integracion);
```

---

## 4. Archivos a Crear por Codex en esta Etapa

1. `backend/migrations/001_initial_schema.sql`: Script SQL idempotente con la estructura arriba detallada.
2. `backend/scripts/test_db_connection.py`: Script para probar la conexión directa o vía pooler contra Supabase usando variables de `.env`.
3. `backend/scripts/seed_demo_users.py`: Script para crear 2 usuarios iniciales de prueba:
   - Solicitante: `solicitante@empresa.com` / `Solicitante123!`
   - Coordinador: `coordinador@empresa.com` / `Coordinador123!`
4. `backend/requirements.txt`: Dependencias mínimas para ejecutar scripts de base de datos (`SQLAlchemy>=2.0`, `asyncpg`, `psycopg2-binary`, `pydantic-settings`, `passlib[bcrypt]`, `python-dotenv`).

---

## 5. Criterios de Aceptación (Verificables)

1. El script SQL se ejecuta contra Supabase (o Postgres local) sin errores de sintaxis y crea las 4 tablas con sus enumerados e índices.
2. `python backend/scripts/test_db_connection.py` conecta a la base de datos e imprime la versión de PostgreSQL.
3. `python backend/scripts/seed_demo_users.py` inserta los 2 usuarios con passwords cifrados mediante bcrypt.
