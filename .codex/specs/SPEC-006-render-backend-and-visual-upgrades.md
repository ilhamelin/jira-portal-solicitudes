# SPEC-006: Despliegue en Render (Backend Cloud) y Mejoras Visuales (Gráficos Recharts, Toasts Sonner y Skeletons)

- **Versión:** 1.0.0
- **Fase:** Optimización y Mejoras de Alto Impacto
- **Estado:** Listo para implementar
- **Responsable de Diseño:** Antigravity (Gemini)
- **Implementador:** Codex (GPT-6.1 Astra)

---

## 1. Objetivo y Contexto

Elevar la calidad técnica y visual del portal a estándares de producción empresarial mediante dos ejes de trabajo:
1. **Infraestructura Cloud del Backend:** Preparar la configuración para desplegar el backend en **Render.com** (usando Docker o Python nativo con endpoint de health check y manifiesto `render.yaml`), permitiendo que el frontend público en Vercel consuma una API HTTPS permanente sin depender del servidor local.
2. **Experiencia de Usuario (UI/UX) Avanzada:**
   - **Gráficos interactivos:** Integrar **Recharts** en el Dashboard (gráfico de dona para distribución de estados y gráfico de barras para áreas).
   - **Sistema de Toasts profesional:** Integrar **Sonner** para notificaciones enriquecidas (ej. toast interactivo con link directo a Jira al crear o sincronizar tickets).
   - **Estados de carga (Skeleton Screens):** Reemplazar spinners genéricos con efectos de carga shimmer en la tabla de solicitudes y en las métricas.
   - **Selector de Tema (Modo Claro / Oscuro):** Switch accesible con persistencia en `localStorage`.

---

## 2. Archivos a Crear / Modificar

```text
jira-portal-solicitudes/
├── render.yaml                           (Nuevo: Configuración de servicio web en Render)
├── backend/
│   ├── app/
│   │   └── main.py                       (Modificar: agregar endpoint GET /health para health checks de Render)
│   └── tests/
│       └── test_health.py                (Nuevo: prueba unitaria para endpoint de health)
└── frontend/
    ├── package.json                      (Modificar: agregar "sonner": "^1.7.0" y "recharts": "^2.15.0")
    ├── src/
    │   ├── App.tsx                       (Modificar: registrar <Toaster richColors position="top-right" />)
    │   ├── components/
    │   │   ├── common/
    │   │   │   ├── Navbar.tsx            (Modificar: agregar ThemeToggle)
    │   │   │   ├── ThemeToggle.tsx       (Nuevo: botón para alternar dark/light mode con icono Sol/Luna)
    │   │   │   └── SkeletonTable.tsx     (Nuevo: filas pulsantes para estados de carga en tablas)
    │   │   └── dashboard/
    │   │       ├── StatusDonutChart.tsx  (Nuevo: gráfico PieChart de Recharts con leyenda y porcentajes)
    │   │       ├── AreaBarChart.tsx      (Nuevo: gráfico BarChart de Recharts para solicitudes por área)
    │   │       └── MetricSkeleton.tsx    (Nuevo: tarjetas shimmer de carga para KPIs)
    │   └── pages/
    │       ├── DashboardPage.tsx         (Modificar: sustituir barras estáticas por gráficos Recharts y skeletons)
    │       ├── NuevaSolicitudPage.tsx    (Modificar: notificar éxito mediante toast de Sonner con botón "Ver en Jira ↗")
    │       └── SolicitudesPage.tsx       (Modificar: usar SkeletonTable durante la carga y toast al sincronizar)
```

---

## 3. Especificación Backend: Manifiesto `render.yaml` y Health Check

### 3.1. Endpoint `/health` (`backend/app/main.py`)
- Endpoint: `GET /health` (Público, sin autenticación).
- Retorno HTTP 200:
  ```json
  {
    "status": "healthy",
    "service": "jira-portal-backend",
    "environment": "production"
  }
  ```

### 3.2. Manifiesto `render.yaml`
```yaml
services:
  - type: web
    name: jira-portal-backend
    runtime: docker
    dockerfilePath: ./backend/Dockerfile
    dockerContext: .
    plan: free
    region: oregon
    healthCheckPath: /health
    envVars:
      - key: PORT
        value: 8000
      - key: DATABASE_URL
        sync: false
      - key: JIRA_INSTANCE_URL
        sync: false
      - key: JIRA_USER_EMAIL
        sync: false
      - key: JIRA_API_TOKEN
        sync: false
      - key: JIRA_PROJECT_KEY
        value: SOL
      - key: JWT_SECRET_KEY
        generateValue: true
      - key: ALLOWED_ORIGINS
        value: https://portal-solicitudes-jira.vercel.app,http://localhost:5173
      - key: ENVIRONMENT
        value: production
```

---

## 4. Especificación Frontend: Gráficos, Toasts y UX

### 4.1. Toasts con Sonner (`src/App.tsx`)
1. Importar `Toaster` y `toast` desde `sonner`:
   ```tsx
   import { Toaster } from 'sonner';
   // En el JSX principal:
   <Toaster position="top-right" richColors closeButton />
   ```
2. **Al crear una solicitud con éxito:**
   ```tsx
   toast.success(`Ticket ${res.jira_integracion.jira_issue_key} creado en Jira`, {
     description: res.titulo,
     action: {
       label: "Abrir en Jira ↗",
       onClick: () => window.open(jiraIssueUrl(res.jira_integracion.jira_issue_key), "_blank")
     }
   });
   ```
3. **Al sincronizar tickets:**
   ```tsx
   toast.info(`Sincronización completada: ${res.total_actualizadas} tickets actualizados.`);
   ```

### 4.2. Gráficos Interactivos Recharts en Dashboard (`DashboardPage.tsx`)
1. **`StatusDonutChart.tsx`:**
   - Componente `PieChart` con radio interior `innerRadius={60}` y `outerRadius={90}`.
   - Colores mapeados al diseño corporativo:
     - `Recibido`: `#94a3b8` (Slate)
     - `En análisis`: `#38bdf8` (Sky)
     - `En desarrollo`: `#818cf8` (Indigo)
     - `En pruebas`: `#fbbf24` (Amber)
     - `Cerrado`: `#10b981` (Emerald)
     - `Rechazado`: `#f87171` (Rose)
   - `Tooltip` formateado con sombras y bordes redondeados.
2. **`AreaBarChart.tsx`:**
   - Componente `BarChart` (`ResponsiveContainer` al 100% de ancho).
   - Eje X: Áreas (`Finanzas`, `Operaciones`, `TI`, etc.).
   - Eje Y: Cantidad de solicitudes.
   - Barra con degradado verde esmeralda y esquinas redondeadas `radius={[6, 6, 0, 0]}`.

### 4.3. Skeleton Loaders (`SkeletonTable.tsx` y `MetricSkeleton.tsx`)
- Efecto shimmer con `animate-pulse` de Tailwind (`bg-slate-200 dark:bg-slate-800`).
- Se muestra mientras `isLoading === true`, eliminando el parpadeo de carga.

### 4.4. Modo Oscuro / Claro (`ThemeToggle.tsx`)
- Lee de `localStorage.getItem('theme')` o preferencia del sistema `prefers-color-scheme`.
- Alterna la clase `'dark'` en el elemento `document.documentElement`.
- Botón estilizado con iconos de `Sun` y `Moon` de `lucide-react`.

---

## 5. Criterios de Aceptación (Verificables)

1. `npm install` instala `sonner` y `recharts` sin conflictos de dependencias.
2. `npm run build` compila el frontend sin advertencias ni errores de tipos de TypeScript.
3. El Dashboard renderiza los dos gráficos de Recharts (`StatusDonutChart` y `AreaBarChart`) con datos dinámicos y responsive.
4. Crear una solicitud dispara el toast interactivo de Sonner con botón de enlace directo a Jira.
5. El switch de modo oscuro alterna los colores de toda la interfaz y persiste al recargar la página.
6. El backend incluye el endpoint `GET /health` que responde HTTP 200 y pasa la prueba en pytest.
