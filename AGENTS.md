# Reglas compartidas de Antigravity y Codex

## Alcance y estado actual

Estas reglas se aplican a todo el proyecto y a ambos agentes. Las instrucciones
explícitas del usuario prevalecen sobre este archivo.

Revisión inicial: 21 de octubre de 2026. Se revisaron `README.md`,
`.codex/CONTEXT.md`, `docs/PLAN_PROYECTO.md` (versión 2), `.env.example`,
`.gitignore` y este archivo.

- Hay documentación y plantillas de entorno; no hay código, dependencias,
  pruebas ni configuración de despliegue.
- No existe `.codex/specs/` ni se encontraron especificaciones. Las carpetas
  `frontend/`, `backend/` y el archivo `docker-compose.yml` del README
  describen una estructura prevista. `docs/` contiene el plan, pero
  `docs/setup.md` todavía no existe.
- La fase actual es revisión y preparación de reglas. No implementar
  funcionalidades, instalar dependencias, crear infraestructura ni desplegar
  hasta que el usuario autorice la siguiente fase.

## Responsabilidades y traspaso

- Antigravity prepara arquitectura, decisiones técnicas, contratos y
  especificaciones en `.codex/specs/SPEC-<num>-<nombre>.md`.
- Codex implementa y prueba el alcance autorizado a partir de una especificación
  vigente y lista para implementar. No debe completar decisiones de arquitectura
  pendientes con suposiciones silenciosas.
- Antigravity Verifier puede realizar una verificación adicional; esa revisión
  no sustituye las pruebas y comprobaciones de Codex.
- Antes de trabajar, leer este archivo, `README.md`, `.codex/CONTEXT.md`,
  `docs/PLAN_PROYECTO.md`, la especificación pertinente y las decisiones que
  esta referencie.
- Si hay contradicciones entre documentos, describirlas y resolverlas antes de
  implementar la parte afectada. No decidir por fecha de archivo o por el agente
  que lo escribió. Continuar el trabajo independiente que sí esté definido.
- Un cambio de contrato debe reflejarse primero en la especificación y, cuando
  corresponda, en el contexto y README. Evitar documentación que describa como
  existente algo que todavía está previsto.

## Base documentada

La documentación propone un portal interno para incidentes y mejoras, con
dashboard y sincronización con Jira Cloud REST API v3:

- Frontend: React 18+, TypeScript, Vite y Tailwind CSS; despliegue en Vercel.
- Backend: Python 3.11+, FastAPI, HTTPX, Pydantic v2 y SQLAlchemy asíncrono.
- Persistencia: PostgreSQL en Supabase. El contexto también enumera Supabase
  Client, pero no define su responsabilidad.

El plan define además:

- Solicitante: autenticarse, crear solicitudes y consultar solo las propias.
- Coordinador: consultar todas las solicitudes, forzar sincronizaciones y
  consultar el dashboard. El equipo técnico opera directamente en Jira.
- Jira es la fuente de verdad del ciclo operativo; el portal refleja sus cambios.
- MVP: formulario, listado paginado, detalle, creación automática en Jira,
  sincronización periódica y manual, registro de intentos y dashboard.
- Modelo inicial: `usuarios`, `solicitudes`, `jira_integraciones` e
  `intentos_integracion`, con respuestas de Jira en JSONB. Aún requiere contratos
  completos, restricciones y migraciones.
- Fuera de v1: adjuntos, comentarios sincronizados bidireccionalmente,
  notificaciones por correo y webhooks entrantes.
- Entorno local previsto con Docker Compose y PostgreSQL; demo pública del
  frontend en Vercel y PostgreSQL gestionado en Supabase.

Esta base no elige el proveedor de identidad ni el destino de despliegue del
backend. Las opciones Render, Railway y Koyeb del plan son alternativas.

## Decisiones pendientes antes de implementar las partes afectadas

Antigravity debe proponer y documentar estas decisiones; el usuario resuelve las
que requieran sus preferencias, acceso a servicios o políticas de la organización.
Para cada decisión registrar alternativa elegida, motivo, consecuencias y estado.
La presencia de una variable en `.env.example` no es una decisión aprobada.

| Tema | Evidencia actual | Definición requerida |
| --- | --- | --- |
| Alcance de Supabase | PostgreSQL está declarado; también se menciona Supabase Client. | Determinar si aporta solo base de datos o también Auth, API de datos u otros servicios. Definir qué usa el cliente y qué usa SQLAlchemy para evitar responsabilidades duplicadas. |
| Acceso a datos | Hay URL de Supabase, claves y `DATABASE_URL`. | Elegir si todo acceso pasa por FastAPI o si el navegador accede a servicios de Supabase. Definir permisos, identidad de cada conexión y dónde se aplica autorización; especificar RLS si corresponde y comprobar los accesos que la eludan. |
| Conexiones y migraciones | El contexto permite pooler en puerto 6543 o conexión directa; la plantilla usa pooler. | Definir conexión de ejecución y de migraciones, controlador asíncrono, compatibilidad con el modo de pool, límites y gestión de sesiones. Definir herramienta y proceso de migraciones. |
| Autenticación | El plan propone `usuarios.password_hash`; la plantilla incluye `JWT_SECRET_KEY` y claves de Supabase. No hay decisión explícita de proveedor. | Elegir autenticación propia, Supabase Auth u otro proveedor y reconciliar el modelo de usuarios. Definir altas, emisor, audiencia, validación en FastAPI, expiración, renovación, cierre de sesión y custodia de sesiones. La autenticación básica de Jira es independiente del login del portal. |
| Autorización | El plan define Solicitante con visibilidad propia y Coordinador con visibilidad global, sincronización y dashboard. | Concretar la matriz de permisos por endpoint, asignación de roles y correspondencia entre identidad y registros. Los filtros de interfaz deben acompañarse de autorización en servidor. |
| Entornos y despliegue | Vercel está indicado para frontend; no se define hosting de FastAPI. | Elegir destino del backend, entornos local/pruebas/producción, orígenes permitidos y proceso de configuración. Resolver ejecución persistente de sincronizaciones y reintentos según el alojamiento elegido. |
| Contrato con Jira | El plan define Incidente y Mejora, creación desde portal y lectura del ciclo operativo desde Jira; la plantilla propone `SOL`. | Confirmar proyecto, IDs de tipos y campos, permisos de la cuenta técnica, mapeo de estados y prioridades, almacenamiento y búsqueda del UUID de correlación. Concretar frecuencia y ejecución del worker y el alcance del endpoint manual. No añadir webhooks en v1. |
| Confiabilidad de integración | Se exige correlación con UUID interno. | Especificar persistencia de intentos, prevención de duplicados ante concurrencia y respuestas inciertas, límites de reintento y recuperación. No asumir que enviar un UUID garantiza idempotencia en Jira. |
| Dashboard y datos temporales | La sección 3 pide estado, prioridad, tipo y solicitudes estancadas; la etapa 4 menciona severidad y tiempo medio desde creación. El modelo de solicitudes no incluye fechas. | Unificar prioridad/severidad y métricas, definir umbral de estancamiento y fórmula del tiempo medio, incorporar las fechas necesarias y concretar permisos de consulta. |
| Criterios de sincronización | La etapa 2 exige `pendiente` ante un corte de red; existen también `fallido` y `reintentando`. La etapa 4 exige reflejar cambios en menos de 3 segundos. | Definir estados por tipo de fallo, política de reintentos y recuperación de creaciones de resultado incierto. Precisar escenario, volumen, inicio y fin de medición del objetivo de 3 segundos y tratamiento de límites de Jira. |
| Respuestas JSONB | El plan pide almacenar la respuesta cruda de Jira. | Definir los datos necesarios para trazabilidad, acceso y retención, y excluir credenciales y datos sensibles innecesarios antes de persistir o mostrar respuestas. |

El plan es una base de alcance, no sustituye las especificaciones implementables.
Las etapas no incluyen un paso explícito para autenticar usuarios del portal,
aunque la etapa 3 lo exige: especificar esa dependencia antes de implementar
operaciones protegidas. Resolver las decisiones pertinentes antes de las
migraciones previstas en la etapa 1. Mantener README, contexto y plantilla de
entorno alineados cuando se cierre cada decisión.

## Condiciones para una especificación implementable

Cada especificación debe incluir:

- Objetivo, alcance y exclusiones, junto con las decisiones y dependencias que
  necesita tener resueltas.
- Contratos de tipos y datos, rutas, métodos, entradas, salidas, errores y
  reglas de validación aplicables.
- Modelo de persistencia y migraciones cuando corresponda; reglas de
  autenticación, permisos y acceso a datos para las operaciones incluidas.
- Estados y transiciones, efectos en Jira, fallos, reintentos y comportamiento
  ante operaciones repetidas cuando aplique.
- Criterios de aceptación observables y verificaciones apropiadas, incluidos
  los casos de fallo relevantes.

No comenzar la parte de una implementación que dependa de una decisión todavía
abierta. Codex puede resolver detalles internos reversibles que respeten los
contratos y debe documentar cualquier supuesto material.

## Invariantes de dominio e integración

- Mantener separados el estado de negocio y el de integración.
- Estados de negocio documentados: `Recibido`, `En análisis`, `En desarrollo`,
  `En pruebas`, `Cerrado`, `Rechazado`.
- Estados de integración documentados: `pendiente`, `sincronizado`, `fallido`,
  `reintentando`.
- El plan define el recorrido `Recibido` → `En análisis` → `En desarrollo` →
  `En pruebas` → `Cerrado`, más `En análisis` → `Rechazado` y
  `En pruebas` → `En desarrollo`. Concretar su correspondencia con Jira y las
  resoluciones obligatorias en la especificación. No añadir transiciones por
  inferencia ni permitir que el portal sustituya a Jira como fuente operativa.
- Usar el UUID interno de la solicitud como correlación con Jira. La
  especificación debe explicar cómo se conserva y se consulta para impedir
  duplicados, incluidos los fallos de red después de una creación remota.
- No cambiar los contratos de datos, rutas o estados para acomodar una
  implementación sin actualizar y resolver antes la especificación afectada.

## Configuración y secretos

- Obtener credenciales mediante variables de entorno; no incluirlas en código,
  documentación, capturas, logs ni resultados de pruebas.
- Mantener `.env.example` con marcadores ficticios y documentar cada variable
  conforme se definan las decisiones; nunca copiar valores reales.
- Credenciales de Jira, claves de servicio de Supabase y credenciales de base de
  datos deben permanecer en el servidor. No exponerlas en el bundle del frontend.
- Cualquier acceso del navegador mediante una clave pública debe contar con
  permisos y políticas de acceso definidos. Una clave pública no sustituye la
  autorización del usuario.
- No reutilizar un secreto JWT propio como sustituto de la validación del
  proveedor de identidad elegido. Documentar qué secretos son necesarios una vez
  decidida la autenticación.
- No publicar, provisionar servicios ni ejecutar cambios contra Jira o bases de
  datos reales como parte de una verificación local sin autorización aplicable.

## Implementación, verificación y entrega

- Implementar solo el incremento autorizado, evitando cambios ajenos al alcance.
- Usar los comandos y herramientas definidos en el proyecto cuando existan;
  no inventar comandos de instalación, pruebas o compilación en los informes.
- Ejecutar las comprobaciones adecuadas al cambio y a sus criterios de
  aceptación. Para integraciones, cubrir fallos, permisos y duplicados con
  dobles de prueba o entornos autorizados según corresponda.
- Informar qué se cambió, qué se verificó realmente, resultados, supuestos y
  bloqueos. No declarar pruebas exitosas si no se ejecutaron.
- No dar por implementadas carpetas previstas, configuraciones o integraciones.
  En esta fase documental no hay una suite de pruebas que ejecutar.
