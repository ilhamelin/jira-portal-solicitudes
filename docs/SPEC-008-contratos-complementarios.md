# Contratos complementarios de SPEC-008

El usuario confirmó el 21 de octubre de 2026 la conservación local con aviso ante
fallos de Jira. La etapa autoriza comentarios bidireccionales pese a su exclusión
en el alcance inicial de v1. Esta entrega no incluye edición, eliminación, workers
ni recepción de comentarios por webhook.

- GET y POST `/api/v1/solicitudes/{id}/comentarios` requieren JWT. Acceso del autor
  y del coordinador; 401 sin sesión, 403 para otro solicitante, 404 si no existe la
  solicitud. POST recibe `ComentarioCreate`, recorta espacios en los extremos y
  valida entre 2 y 2000 caracteres (422).
- POST persiste primero el comentario local y luego realiza un único envío a Jira
  cuando existe una clave de ticket, independientemente del estado de integración.
  Responde 201 con `ComentarioResponse`. Si Jira falla o la respuesta es incierta,
  conserva `jira_comment_id: null`. Sin ticket también guarda solo en el portal.
  La interfaz muestra «Guardado solo en el portal» y no reenvía automáticamente.
- GET consulta todas las páginas de Jira, importa los comentarios nuevos y devuelve
  `list[ComentarioResponse]` ordenada por `created_at`, con ID como desempate. Un
  fallo de consulta o un payload inválido conserva la lista local y devuelve 200.
  La cabecera expuesta por CORS `X-Jira-Comments-Sync` indica `ok`, `failed` o
  `not-linked`. El frontend muestra un aviso cuando el valor es `failed`.
- El ADF saliente conserva el prefijo `[Portal - Nombre]: texto` de la SPEC y añade
  la propiedad de comentario `portal_comment_id` con el UUID local. El GET solicita
  `expand=properties`. Esto permite reconocer ecos y reconciliar un envío que Jira
  aceptó antes de un timeout, sin repetir el POST. El nombre o un prefijo escrito
  por un técnico no bastan para atribuir un comentario al portal.
- Un índice único por `(solicitud_id, jira_comment_id)` protege de importaciones
  duplicadas. Se serializa la importación por solicitud en PostgreSQL. Las fechas
  entrantes se toman de `created` en Jira, normalizadas a UTC. No se importan
  respuestas parciales si falla una página. El recorrido tiene un límite defensivo
  de 1000 páginas; superarlo conserva los datos locales y devuelve aviso.
- Solo se importan comentarios públicos, sin `visibility` restrictiva ni propiedad
  de comentario interno. Si una consulta exitosa detecta que un comentario de Jira
  previamente importado ahora es restringido, se retira de la copia local. Durante
  una caída de Jira se devuelve la última copia conocida, sin poder comprobar
  cambios de visibilidad. No se sincronizan ediciones ni eliminaciones generales.
- El ADF entrante se presenta como texto, conservando párrafos, listas y saltos de
  línea; no se ejecuta HTML ni se descargan archivos. La longitud de 2000 limita
  las publicaciones del portal; los textos importados conservan su longitud.
- Añadir comentarios no cambia las fechas del ciclo operativo ni las métricas de
  solicitudes estancadas. No se añaden tipos de operación a la auditoría existente;
  la tabla de comentarios conserva autor, origen e identificador remoto.

La migración `backend/migrations/003_add_comentarios_table.sql` activa RLS sin
políticas públicas. Su aplicación y las pruebas con Jira real quedan fuera de la
verificación local. Las pruebas de integración usan SQLite y dobles HTTP.
