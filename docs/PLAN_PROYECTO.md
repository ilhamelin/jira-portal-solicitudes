# Plan del Portal de Solicitudes Internas Integrado con Jira
**Planificación del Proyecto de Portafolio — Versión 2 (Cloud Ready)**  
*Fecha: 21 de octubre de 2026*

---

## 1. Objetivo y Contexto
Construir una solución completa para una empresa ficticia donde los colaboradores registren incidentes y requerimientos de mejora, el equipo técnico gestione el ciclo de vida en Jira Cloud y la coordinación consulte métricas en un dashboard.

El proyecto busca demostrar competencias directas para la vacante **Desarrollador Junior Integraciones con JIRA** en Haibu Solutions. Esta versión incorpora despliegue en la nube (**Vercel** para frontend con CI/CD y **Supabase** como base de datos PostgreSQL gestionada), permitiendo presentar una **demo funcional en vivo con URL pública** junto al entorno local reproducible.

---

## 2. Usuarios y Responsabilidades

| Perfil | Responsabilidades |
| :--- | :--- |
| **Solicitante** | Autenticarse, crear solicitudes y consultar el estado únicamente de las propias. |
| **Coordinador** | Consultar todas las solicitudes, forzar sincronizaciones manuales y analizar el dashboard. |
| **Equipo Técnico** | Clasificar, asignar responsables, priorizar y resolver tickets directamente en Jira. |

---

## 3. Alcance de la Primera Versión (MVP)

* **Autenticación y Autorización:** Roles diferenciados (`Solicitante` y `Coordinador`).
* **Gestión de Solicitudes:** Formulario, listado paginado y vista de detalle (Incidentes y Mejoras).
* **Integración con Jira Cloud (REST API v3):**
  - Creación automática de tickets con mapeo de campos.
  - Mecanismo de **idempotencia** mediante identificador único (`UUID`) para evitar tickets duplicados ante fallas de red.
* **Sincronización:**
  - Sincronización periódica programada.
  - Botón de **"Sincronizar ahora"** en la interfaz para demostraciones en tiempo real.
* **Resiliencia y Monitoreo:**
  - Separación explícita del estado de negocio vs. estado de integración.
  - Registro detallado de intentos de integración y respuesta cruda (*payload*) de Jira en formato JSONB.
* **Dashboard:** Métricas por estado, prioridad, tipo y solicitudes estancadas.
* **Despliegue Cloud:** Frontend disponible públicamente en Vercel y base de datos en Supabase.

*Fuera de la v1 (para v2):* Adjuntos, comentarios sincronizados bidireccionalmente, notificaciones por correo y webhooks entrantes.

---

## 4. Recorrido Operativo y Flujo en Jira

- **Flujo de estados en Jira:**  
  `Recibido` → `En análisis` → `En desarrollo` → `En pruebas` → `Cerrado`.  
  *(Caminos alternativos: `En análisis` → `Rechazado` y devolución de `En pruebas` → `En desarrollo`).*
- **Regla de oro:** Jira es la fuente de verdad del ciclo operativo; el portal refleja las transiciones mediante la sincronización.

---

## 5. Arquitectura del Sistema

| Componente | Tecnología | Propósito | Despliegue |
| :--- | :--- | :--- | :--- |
| **Frontend** | React, TypeScript, Vite, Tailwind CSS | Portal de usuarios y dashboard interactivo. | **Vercel** (Edge CDN + CI/CD automático). |
| **Backend** | Python, FastAPI, Pydantic v2, HTTPX / SQLAlchemy | API REST, lógica de permisos, conexión a Jira. | Render / Railway / Koyeb *(o contenedor Docker)*. |
| **Base de Datos** | **Supabase (PostgreSQL 15+)** | Persistencia, pooling de conexiones (Supavisor) y auditoría. | **Supabase Cloud** *(+ Docker Postgres para local)*. |
| **Gestión** | Jira Software Cloud (Free Tier) | Tablero Kanban, flujos de trabajo y transiciones. | Atlassian Cloud. |
| **Entorno Local** | Docker & Docker Compose | Orquestación local reproducible de frontend, backend y DB. | `localhost`. |

---

## 6. Modelo de Datos Inicial (Supabase)

1. **`usuarios`**: `id (UUID)`, `email`, `nombre`, `rol (solicitante|coordinador)`, `password_hash`, `created_at`.
2. **`solicitudes`**:
   - `id (UUID)` (utilizado como `external_id` idempotente en Jira).
   - `autor_id (FK)`, `titulo`, `descripcion`, `tipo (incidente|mejora)`, `area`, `prioridad_solicitada`.
   - `estado_negocio` (`Recibido`, `En análisis`, `En desarrollo`, `En pruebas`, `Cerrado`, `Rechazado`).
   - `prioridad_definitiva`, `responsable_jira`.
3. **`jira_integraciones`**:
   - `solicitud_id (FK)`, `jira_issue_id`, `jira_issue_key` (ej. `SOL-101`), `ultima_sincronizacion_at`.
   - `estado_integracion` (`pendiente`, `sincronizado`, `fallido`, `reintentando`).
4. **`intentos_integracion`** *(Trazabilidad técnica)*:
   - `id`, `solicitud_id (FK)`, `operacion` (`CREATE_ISSUE`, `SYNC_STATUS`), `http_status`, `error_mensaje`, `payload_respuesta (JSONB)`, `fecha`.

---

## 7. Etapas y Criterios de Aceptación

### Etapa 1: Configuración de Jira Cloud y Supabase
- Crear proyecto en Jira Software Cloud con tipos de ticket: *Incidente* y *Mejora*.
- Configurar workflow con transiciones y resoluciones obligatorias.
- Configurar proyecto en Supabase, ejecutar migraciones de tablas iniciales y verificar el pooler de conexiones (puerto `6543`).
- **Criterio de aceptación:** Crear y transicionar un ticket manualmente en Jira; verificar conexión exitosa a Supabase vía script de prueba.

### Etapa 2: Motor de Integración Backend (FastAPI + Jira API)
- Configurar FastAPI con autenticación básica de Jira (`email` + `API Token`).
- Implementar servicio de creación de tickets con verificación previa para garantizar idempotencia.
- Manejar reintentos y capturar excepciones (401, 404, 429 de Jira).
- **Criterio de aceptación:** Una solicitud creada mediante `/api/solicitudes` genera un ticket real en Jira y registra el `jira_issue_key` y el `JSONB` de respuesta en Supabase. Si se simula un corte de red, la solicitud queda marcada como `pendiente`.

### Etapa 3: Portal Web y Despliegue en Vercel
- Desarrollar interfaz con React, TypeScript y Tailwind CSS: Login, formulario de creación y vista de solicitudes con filtros por rol.
- Conectar el repositorio de GitHub con **Vercel** para despliegue continuo (CI/CD).
- **Criterio de aceptación:** Frontend disponible en URL pública que permite autenticarse como Solicitante (ver solo sus tickets) o Coordinador (ver todo).

### Etapa 4: Sincronización y Dashboard
- Implementar endpoint y worker para sincronizar estado y responsable desde Jira.
- Añadir botón **"Sincronizar ahora"** en el portal.
- Construir el Dashboard con métricas: solicitudes por estado, por severidad y tiempo medio desde creación.
- **Criterio de aceptación:** Modificar el estado de un ticket en Jira, pulsar "Sincronizar ahora" en el portal y observar el cambio reflejado en menos de 3 segundos con los gráficos actualizados.

### Etapa 5: Resiliencia, Documentación y Demo Final
- Pruebas de recuperación ante errores de API de Jira.
- Preparar el `README.md` técnico con diagrama de arquitectura, variables de entorno de ejemplo (`.env.example`) y guía de ejecución local con Docker.
- Grabar video demo (2–3 min) mostrando el ciclo de vida completo.
