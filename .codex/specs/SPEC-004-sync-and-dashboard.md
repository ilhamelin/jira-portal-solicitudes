# SPEC-004: Sincronización Bidireccional con Jira Cloud y Dashboard de Métricas

- **Versión:** 1.0.0
- **Fase:** Etapa 4 (Sincronización y Dashboard)
- **Estado:** Listo para implementar
- **Responsable de Diseño:** Antigravity (Gemini)
- **Implementador:** Codex (GPT-6.1 Astra)

---

## 1. Objetivo y Contexto

Implementar el flujo de sincronización bajo demanda desde **Jira Cloud hacia el Portal** (activable mediante botón en la UI y endpoints REST, ideal para demostraciones deterministas en tiempo real) para reflejar los cambios de estado y asignación de responsables ejecutados por el equipo técnico en Jira. Además, construir el **Dashboard de Gestión para el Coordinador** con métricas clave, distribución de solicitudes y detección de tickets estancados. El worker periódico queda reservado para la etapa de despliegue.

---

## 2. Archivos a Crear / Modificar

```text
backend/
├── app/
│   ├── schemas/
│   │   ├── dashboard.py                  (Nuevo: DashboardMetricsResponse, EstadoCount, etc.)
│   │   └── jira.py                       (Modificar: SyncResultSchema)
│   ├── services/
│   │   ├── jira_client.py                (Modificar: get_issue_status, sync_all_active_issues)
│   │   └── dashboard_service.py          (Nuevo: Consultas analíticas SQL para métricas)
│   ├── api/v1/
│   │   ├── solicitudes.py                (Modificar: POST /api/v1/solicitudes/{id}/sync)
│   │   ├── jira.py                       (Nuevo: POST /api/v1/jira/sync para sincronización masiva)
│   │   └── dashboard.py                  (Nuevo: GET /api/v1/dashboard/metrics)
│   └── main.py                           (Registrar nuevos routers de jira y dashboard)
└── tests/
    └── test_sync_and_dashboard.py        (Nuevas pruebas unitarias de sync y métricas)

frontend/
├── src/
│   ├── types/
│   │   └── index.ts                      (Extender con DashboardMetrics, SyncResponse)
│   ├── services/
│   │   ├── api.ts                        (Agregar syncSolicitud, syncAllJira, getDashboardMetrics)
│   ├── components/
│   │   ├── common/
│   │   │   └── Navbar.tsx                (Agregar enlace a Dashboard condicionado a rol 'coordinador')
│   │   └── dashboard/
│   │       ├── MetricCard.tsx            (Tarjeta KPI con icono, número y tendencia)
│   │       ├── BarChartSimple.tsx        (Barras porcentuales accesibles con Tailwind)
│   │       └── StalledAlertCard.tsx      (Alerta de solicitudes estancadas > 5 días)
│   └── pages/
│       ├── DashboardPage.tsx             (Vista completa de métricas para el Coordinador)
│       ├── SolicitudesPage.tsx           (Añadir botón 'Sincronizar con Jira' con animación de refresh)
│       └── DetalleSolicitudPage.tsx      (Añadir botón 'Sincronizar ticket actual')
```

---

## 3. Contratos de Datos

### 3.1. Backend (`app/schemas/dashboard.py`)
```python
from datetime import datetime
from typing import Dict, Optional
from pydantic import BaseModel

class DashboardMetricsResponse(BaseModel):
    total_solicitudes: int
    tasa_resolucion_pct: float
    solicitudes_estancadas: int
    por_estado: Dict[str, int]
    por_tipo: Dict[str, int]
    por_prioridad: Dict[str, int]
    por_area: Dict[str, int]
    ultima_sincronizacion_general: Optional[datetime]
```

### 3.2. Sincronización (`app/schemas/jira.py`)
```python
class SyncResultResponse(BaseModel):
    solicitud_id: str
    jira_issue_key: str
    estado_anterior: str
    estado_nuevo: str
    responsable_jira: Optional[str]
    hubo_cambios: bool

class BulkSyncResponse(BaseModel):
    total_revisadas: int
    total_actualizadas: int
    detalles: list[SyncResultResponse]
    timestamp: datetime
```

### 3.3. Frontend (`src/types/index.ts`)
```typescript
export interface DashboardMetrics {
  total_solicitudes: number;
  tasa_resolucion_pct: number;
  solicitudes_estancadas: number;
  por_estado: Record<EstadoNegocio, number>;
  por_tipo: Record<TipoSolicitud, number>;
  por_prioridad: Record<PrioridadTipo, number>;
  por_area: Record<string, number>;
  ultima_sincronizacion_general: string | null;
}

export interface SyncResult {
  solicitud_id: string;
  jira_issue_key: string;
  estado_anterior: string;
  estado_nuevo: string;
  responsable_jira: string | null;
  hubo_cambios: boolean;
}

export interface BulkSyncResponse {
  total_revisadas: number;
  total_actualizadas: number;
  detalles: SyncResult[];
  timestamp: string;
}
```

---

## 4. Algoritmos y Reglas de Negocio

### 4.1. Mapeo de Estados de Jira a Estado de Negocio del Portal
Jira puede tener nombres de estado en español o inglés dependiendo de la configuración. La función de normalización debe mapear:

| Estado en Jira (Case-insensitive) | Estado de Negocio en Portal |
| :--- | :--- |
| `Backlog`, `Por hacer`, `To Do`, `Recibido`, `Abierto` | `Recibido` |
| `Seleccionado para desarrollo`, `En análisis`, `In Analysis`, `Under Review` | `En análisis` |
| `En curso`, `In Progress`, `En desarrollo` | `En desarrollo` |
| `En pruebas`, `Testing`, `QA`, `En revisión` | `En pruebas` |
| `Listo`, `Done`, `Finalizado`, `Cerrado`, `Resuelto` | `Cerrado` |
| `Rechazado`, `Descartado`, `Won't Do`, `Cancelado` | `Rechazado` |

*Efecto secundario al cerrar:* Si el nuevo estado es `Cerrado` o `Rechazado`, se asigna `closed_at = NOW()`. Si se reabre, se asigna `closed_at = NULL`.

### 4.2. Algoritmo de Sincronización Individual (`POST /api/v1/solicitudes/{id}/sync`)
1. Consultar la solicitud y su `jira_integraciones` por `id`.
2. Si no tiene `jira_issue_key` o `estado_integracion != 'sincronizado'`, retornar error 400.
3. Consultar a Jira REST API v3: `GET /rest/api/3/issue/{jira_issue_key}?fields=status,assignee,priority`.
4. Extraer el nombre del estado y el nombre del responsable (`assignee.displayName` o `None`).
5. Mapear estado al `EstadoNegocio`.
6. Si hay cambios en `estado_negocio` o `responsable_jira`:
   - Actualizar registro en `solicitudes` (`estado_negocio`, `responsable_jira`, `updated_at = NOW()`).
7. Actualizar `jira_integraciones.ultima_sincronizacion_at = NOW()`.
8. Insertar en `intentos_integracion` auditoría de tipo `SYNC_STATUS` con HTTP 200 y el payload recibido.
9. Retornar `SyncResultResponse`.

### 4.3. Reglas de Cálculo para el Dashboard (`dashboard_service.py`)
- **Solicitudes Estancadas:** Cantidad de solicitudes donde:
  `estado_negocio NOT IN ('Cerrado', 'Rechazado') AND updated_at < NOW() - INTERVAL '5 days'`.
- **Tasa de Resolución:** `(solicitudes_cerradas / total_solicitudes) * 100` (redondeado a 1 decimal). Si el total es 0, retornar `0.0`.
- **Acceso:** Solo usuarios con `rol == 'coordinador'`. Solicitantes reciben `HTTP 403 Forbidden`.

---

## 5. Requerimientos de UI en Frontend

### 5.1. Botón "Sincronizar con Jira"
- Ubicado en la barra superior de filtros de `SolicitudesPage` y en el encabezado de `DetalleSolicitudPage`.
- Al pulsarse:
  - Muestra un spinner animado girando en el botón.
  - Al completar, actualiza los datos en pantalla de inmediato sin recargar toda la página.
  - Muestra un toast/notificación: *"Sincronización completada: X tickets actualizados"*.

### 5.2. Página `DashboardPage.tsx` (Ruta `/dashboard`)
- Tarjetas de resumen destacadas:
  - 📊 **Total Solicitudes** (contador grande).
  - 🎯 **Tasa de Resolución** (porcentaje con barra de progreso).
  - ⚠️ **Solicitudes Estancadas** (con badge ámbar o rojo si > 0).
  - 🔄 **Última Sincronización** (hora legible).
- Gráficos de barras porcentuales Tailwind:
  - Distribución por Estado (`Recibido`, `En análisis`, `En desarrollo`, `En pruebas`, `Cerrado`).
  - Distribución por Tipo (`Incidentes` vs `Mejoras`).
  - Distribución por Área (Finanzas, Operaciones, TI, etc.).

---

## 6. Criterios de Aceptación (Verificables)

1. **Sincronización:**
   - Cambiar manualmente el estado de un ticket en Jira Cloud (ej. `SOL-1` a *"En curso"* o *"Listo"*).
   - Presionar el botón "Sincronizar" en el portal; el estado en el portal cambia automáticamente al correspondiente sin errores.
2. **Dashboard:**
   - Un usuario con rol `coordinador` puede navegar a `/dashboard` y visualizar métricas consistentes con la base de datos de Supabase.
   - Un usuario con rol `solicitante` no ve el enlace a Dashboard en el Navbar y es redirigido a `/solicitudes` si intenta entrar manualmente.
3. **Pruebas Automatizadas:**
   - `pytest` ejecuta pruebas unitarias para el endpoint de sincronización y el cálculo de métricas con cobertura de casos borde (0 solicitudes, estados desconocidos, división por cero).

## 7. Aclaraciones de esta entrega

- El usuario confirmó que esta etapa incluye **solo sincronización manual**;
  no se incorpora un worker ni una frecuencia periódica.
- Se mantienen los permisos del plan: el coordinador ejecuta sincronizaciones
  individuales/masivas y consulta el dashboard; los solicitantes conservan la
  consulta de sus solicitudes y no reciben acceso a estas operaciones.
- La sincronización masiva revisa tickets activos, vinculados y con integración
  `sincronizado`. Los terminales se pueden consultar individualmente para detectar
  una reapertura. No se reintentan creaciones de tickets fallidas.
- Un fallo de consulta o estado desconocido conserva los datos locales y el
  vínculo; se audita `SYNC_STATUS`. El endpoint individual retorna 502. En la
  operación masiva se continúa con los demás tickets: `total_revisadas` incluye
  todos los intentados y `detalles` contiene solo los consultados correctamente;
  la diferencia permite notificar fallos parciales sin extender el contrato.
- `updated_at` solo avanza al cambiar estado o responsable. La fecha de cierre
  se conserva ante consultas repetidas del mismo estado terminal y se limpia
  al reabrir. La consulta sin cambios actualiza únicamente la sincronización y
  su auditoría, para no ocultar solicitudes estancadas.
- La distribución por prioridad usa la definitiva cuando existe, y en otro caso
  la solicitada. Esta sincronización modifica estado y responsable conforme al
  algoritmo 4.2; no agrega cambios de prioridad al portal.
- La última sincronización del dashboard es el máximo
  `jira_integraciones.ultima_sincronizacion_at`. Se devuelven ceros para todas
  las categorías conocidas cuando no hay solicitudes, incluido `Rechazado`.
