# Contratos complementarios de SPEC-007

La SPEC-007 autoriza webhooks y adjuntos para esta etapa avanzada; prevalece sobre
su exclusión en el alcance inicial de v1. La descarga protegida en FastAPI fue
confirmada por el usuario el 21 de octubre de 2026.

## Adjuntos

- `POST /api/v1/solicitudes/{id}/adjuntos`: Bearer JWT y multipart con un campo
  `file`; devuelve 201 con `AdjuntoResponse`. Autor o coordinador; los otros
  solicitantes reciben 403. Una solicitud inexistente devuelve 404 y un ticket
  sin vínculo sincronizado devuelve 409.
- `GET /api/v1/solicitudes/{id}/adjuntos`: mismos permisos; devuelve la lista de
  `AdjuntoResponse`, ordenada por creación e ID. No incluye URLs ni credenciales.
- `GET /api/v1/solicitudes/{id}/adjuntos/{adjunto_id}/descarga`: mismos permisos;
  devuelve el archivo como descarga, consultando el ID de Jira por el servidor.
  Un adjunto que no pertenece a esa solicitud devuelve 404. No se siguen URLs
  arbitrarias ni redirecciones de Jira.
- PNG, JPEG, PDF y TXT UTF-8; se validan extensión, MIME, contenido básico, nombre
  seguro de hasta 255 caracteres y tamaño entre 1 byte y 10 MiB (10 × 1024²).
  Tamaño excedido: 413; formato no permitido: 415; nombre/contenido vacío: 422.
  Errores de Jira o respuesta remota inválida: 502, sin registrar éxito local.
- Jira almacena los binarios; PostgreSQL conserva metadatos. La migración canónica
  es `backend/migrations/002_add_adjuntos_table.sql`, siguiendo el apartado 3.1
  de la especificación (el árbol del apartado 2 contiene una ruta distinta).
- El formulario crea primero la solicitud y después envía los archivos de forma
  secuencial. Un fallo de adjunto nunca vuelve a crear la solicitud. Se muestran
  los archivos no enviados, y se permite descargarlos localmente para conservarlos.
  No hay reintentos automáticos: tras un timeout, comprobar el ticket en Jira
  antes de volver a subir, ya que el resultado remoto puede ser incierto.
- Solo se muestran los adjuntos enviados por el portal en esta etapa; el webhook
  no importa archivos añadidos directamente en Jira. No hay eliminación ni
  almacenamiento durable de archivos pendientes en el portal.

## Webhook

- `POST /api/v1/webhooks/jira`: secreto independiente `JIRA_WEBHOOK_SECRET`,
  comparado en tiempo constante. Cabecera `X-Webhook-Secret` o query `token`;
  si están ambos, prevalece la cabecera. Se recomienda la cabecera cuando el
  emisor lo permita para evitar tokens en logs de URLs. Secreto ausente: 401.
- Se aplica `jira:issue_updated`; requiere clave, estado y `assignee` explícito
  (puede ser null). JSON/campos inválidos y estados sin mapeo: 422; límite de
  evento: 1 MiB (413). Otros eventos y tickets sin vínculo: 200 `ignored`.
- Los eventos válidos actualizan estado, responsable, fechas y sincronización,
  y registran `SYNC_STATUS` en una sola transacción. No hacen peticiones a Jira.
  El cuerpo auditado incluye solo clave, estado y responsable sanitizados.
- Repetir un evento sin cambios conserva `updated_at` y `closed_at`; cada entrega
  se audita. La SPEC-007 no define un identificador ni un cursor de versión:
  no se garantiza deduplicación de auditorías ni orden de eventos retrasados.
- El objetivo de 200 ms corresponde al procesamiento local sin llamadas remotas;
  no constituye una garantía de latencia de red o de Supabase en producción.

Las comprobaciones usan SQLite y dobles HTTP. La migración, el registro del
webhook en Jira y las subidas reales requieren un entorno autorizado; no se
ejecutan como parte de la verificación local.
