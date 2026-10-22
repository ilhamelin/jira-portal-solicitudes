-- SPEC-001: ejecutar sobre una base nueva; se puede repetir sin borrar datos.
-- IF NOT EXISTS no modifica objetos preexistentes con una definición diferente.
BEGIN;

-- Supabase puede tener uuid-ossp instalado previamente en extensions.
SET LOCAL search_path TO public, extensions, pg_catalog;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA public;

DO $$
BEGIN
    CREATE TYPE rol_usuario AS ENUM ('solicitante', 'coordinador');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    CREATE TYPE tipo_solicitud AS ENUM ('incidente', 'mejora');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    CREATE TYPE prioridad_tipo AS ENUM ('baja', 'media', 'alta', 'urgente');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    CREATE TYPE estado_negocio_tipo AS ENUM (
        'Recibido', 'En análisis', 'En desarrollo', 'En pruebas',
        'Cerrado', 'Rechazado'
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    CREATE TYPE estado_integracion_tipo AS ENUM (
        'pendiente', 'sincronizado', 'fallido', 'reintentando'
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    CREATE TYPE operacion_integracion_tipo AS ENUM (
        'CREATE_ISSUE', 'SYNC_STATUS', 'UPDATE_PRIORITY'
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS usuarios (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    nombre VARCHAR(150) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    rol rol_usuario NOT NULL DEFAULT 'solicitante',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS solicitudes (
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

CREATE TABLE IF NOT EXISTS jira_integraciones (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    solicitud_id UUID UNIQUE NOT NULL REFERENCES solicitudes(id) ON DELETE CASCADE,
    jira_issue_id VARCHAR(50) NULL,
    jira_issue_key VARCHAR(50) NULL,
    estado_integracion estado_integracion_tipo NOT NULL DEFAULT 'pendiente',
    ultima_sincronizacion_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS intentos_integracion (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    solicitud_id UUID NOT NULL REFERENCES solicitudes(id) ON DELETE CASCADE,
    operacion operacion_integracion_tipo NOT NULL,
    http_status INT NULL,
    error_mensaje TEXT NULL,
    payload_respuesta JSONB NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_solicitudes_autor ON solicitudes(autor_id);
CREATE INDEX IF NOT EXISTS idx_solicitudes_estado ON solicitudes(estado_negocio);
CREATE INDEX IF NOT EXISTS idx_jira_integraciones_key ON jira_integraciones(jira_issue_key);
CREATE INDEX IF NOT EXISTS idx_jira_integraciones_estado ON jira_integraciones(estado_integracion);

COMMIT;
