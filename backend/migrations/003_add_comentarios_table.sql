BEGIN;

CREATE TABLE IF NOT EXISTS solicitud_comentarios (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    solicitud_id UUID NOT NULL REFERENCES solicitudes(id) ON DELETE CASCADE,
    autor_id UUID NULL REFERENCES usuarios(id) ON DELETE SET NULL,
    autor_nombre VARCHAR(150) NOT NULL,
    origen VARCHAR(20) NOT NULL DEFAULT 'portal',
    contenido TEXT NOT NULL,
    jira_comment_id VARCHAR(50) NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_comentarios_solicitud ON solicitud_comentarios(solicitud_id);
-- Un ID remoto se importa una sola vez por solicitud; los pendientes permiten NULL.
CREATE UNIQUE INDEX IF NOT EXISTS uq_comentarios_jira
    ON solicitud_comentarios(solicitud_id, jira_comment_id);

ALTER TABLE solicitud_comentarios ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON solicitud_comentarios FROM PUBLIC;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON solicitud_comentarios FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE ALL ON solicitud_comentarios FROM authenticated;
    END IF;
END $$;

COMMIT;
