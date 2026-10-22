BEGIN;

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

-- El navegador accede mediante FastAPI; no se conceden políticas públicas.
ALTER TABLE solicitud_adjuntos ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON solicitud_adjuntos FROM PUBLIC;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON solicitud_adjuntos FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE ALL ON solicitud_adjuntos FROM authenticated;
    END IF;
END $$;

COMMIT;
