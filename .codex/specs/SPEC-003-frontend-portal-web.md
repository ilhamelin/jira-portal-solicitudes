# SPEC-003: Portal Web en React + TypeScript y Configuración para Vercel

- **Versión:** 1.0.0
- **Fase:** Etapa 3 (Portal Web y Despliegue en Vercel)
- **Estado:** Listo para implementar
- **Responsable de Diseño:** Antigravity (Gemini)
- **Implementador:** Codex (GPT-6.1 Astra)

---

## 1. Objetivo y Contexto

Construir una Single Page Application (SPA) moderna, accesible y responsiva utilizando **React 18+**, **TypeScript**, **Vite** y **Tailwind CSS**. La aplicación consumirá los endpoints de la API de FastAPI desarrollada en `SPEC-002`, implementará control de acceso basado en roles (`solicitante` y `coordinador`) y contará con la configuración lista para despliegue inmediato en **Vercel**.

---

## 2. Archivos a Crear en `frontend/`

```text
frontend/
├── index.html
├── package.json                          (React, react-dom, react-router-dom, lucide-react, tailwindcss, etc.)
├── vite.config.ts
├── tailwind.config.js
├── postcss.config.js
├── tsconfig.json
├── tsconfig.node.json
├── vercel.json                           (Reglas de reescritura SPA para Vercel)
├── .env.example                          (VITE_API_URL="http://localhost:8000/api/v1")
└── src/
    ├── main.tsx
    ├── App.tsx                           (Router y proveedores de contexto)
    ├── index.css                         (Directivas Tailwind)
    ├── types/
    │   └── index.ts                      (Contratos de tipos TypeScript idénticos a Pydantic)
    ├── services/
    │   ├── api.ts                        (Cliente HTTP fetch/axios con inyección de JWT y manejo de 401)
    │   └── auth.ts                       (Manejo de tokens en localStorage y estado de sesión)
    ├── context/
    │   └── AuthContext.tsx               (Contexto global de usuario y métodos login/logout)
    ├── components/
    │   ├── common/
    │   │   ├── Navbar.tsx                (Header con usuario activo, badge de rol y botón salir)
    │   │   ├── StatusBadge.tsx           (Etiquetas visuales para estado de negocio e integración)
    │   │   └── ProtectedRoute.tsx        (Guarda de rutas por autenticación y rol)
    │   └── solicitudes/
    │       ├── SolicitudCard.tsx         (Ficha de solicitud para listas)
    │       └── WorkflowStepper.tsx       (Barra de progreso visual de las fases de Jira)
    └── pages/
        ├── LoginPage.tsx                 (Formulario con botones de acceso rápido para demo)
        ├── SolicitudesPage.tsx           (Listado con filtros por estado, tipo y búsqueda)
        ├── NuevaSolicitudPage.tsx        (Formulario de creación con validaciones)
        └── DetalleSolicitudPage.tsx      (Detalle completo, vínculo a Jira y log de auditoría)
```

---

## 3. Contratos de Tipos Estrictos (`src/types/index.ts`)

```typescript
export type RolUsuario = 'solicitante' | 'coordinador';

export interface Usuario {
  id: string;
  email: string;
  nombre: string;
  rol: RolUsuario;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user_id: string;
  rol: RolUsuario;
  nombre: string;
}

export type TipoSolicitud = 'incidente' | 'mejora';
export type PrioridadTipo = 'baja' | 'media' | 'alta' | 'urgente';
export type EstadoNegocio = 
  | 'Recibido' 
  | 'En análisis' 
  | 'En desarrollo' 
  | 'En pruebas' 
  | 'Cerrado' 
  | 'Rechazado';

export type EstadoIntegracion = 'pendiente' | 'sincronizado' | 'fallido' | 'reintentando';

export interface JiraIntegracion {
  jira_issue_key: string | null;
  estado_integracion: EstadoIntegracion;
  ultima_sincronizacion_at: string | null;
}

export interface Solicitud {
  id: string;
  titulo: string;
  tipo: TipoSolicitud;
  area: string;
  prioridad_solicitada: PrioridadTipo;
  prioridad_definitiva: PrioridadTipo | null;
  estado_negocio: EstadoNegocio;
  responsable_jira: string | null;
  created_at: string;
  jira_integracion?: JiraIntegracion | null;
}

export interface IntentoAuditoria {
  id: string;
  operacion: string;
  http_status: number | null;
  error_mensaje: string | null;
  payload_respuesta?: Record<string, unknown> | null;
  created_at: string;
}

export interface SolicitudDetalle extends Solicitud {
  descripcion: string;
  autor_email: string;
  autor_nombre: string;
  intentos_recientes: IntentoAuditoria[];
}

export interface SolicitudCreateInput {
  titulo: string;
  descripcion: string;
  tipo: TipoSolicitud;
  area: string;
  prioridad_solicitada: PrioridadTipo;
}
```

---

## 4. Requerimientos de UX / UI y Páginas

### 4.1. Página de Login (`LoginPage.tsx`)
- Formulario de `email` y `password` conectado a `POST /api/v1/auth/login`.
- **Botones de Relleno Rápido (Esenciales para Demos de Selección):**
  - Botón: *"Ingresar como Solicitante Demo"* (rellena `solicitante@empresa.com` / `Solicitante123!`).
  - Botón: *"Ingresar como Coordinador Demo"* (rellena `coordinador@empresa.com` / `Coordinador123!`).
- Muestra mensajes de error claros ante credenciales inválidas.

### 4.2. Listado de Solicitudes (`SolicitudesPage.tsx`)
- Muestra tabla o tarjetas con: Título, Tipo (con ícono representativo), Área, Prioridad, Estado de Negocio y **Badge de Jira** (ej. `SOL-1` con enlace externo a `https://portal-solicitudes-dev.atlassian.net/browse/SOL-X`).
- Indicador visual del estado de sincronización:
  - `sincronizado`: Verde con check.
  - `pendiente`: Amarillo/reloj.
  - `fallido`: Rojo con advertencia.
- Filtros interactivos por Tipo (`Todos`, `Incidente`, `Mejora`) y búsqueda por texto en tiempo real.
- Botón destacado: **"+ Nueva Solicitud"**.

### 4.3. Formulario de Creación (`NuevaSolicitudPage.tsx`)
- Campos:
  - Título (input texto, mínimo 5 caracteres).
  - Área (select: *Finanzas, Operaciones, Ventas, TI, Recursos Humanos, Logística*).
  - Tipo (radio o select: *Incidente* [icono bug] o *Mejora* [icono mejora]).
  - Prioridad solicitada (select: *Baja, Media, Alta, Urgente*).
  - Descripción (textarea amplio, mínimo 10 caracteres).
- Estado de carga durante el submit: *"Registrando en base de datos y creando ticket en Jira Cloud..."*.
- Al finalizar con éxito, muestra un modal o alerta con la clave del ticket creado (ej. `SOL-2`) y botón para ir al detalle o al tablero de Jira.

### 4.4. Detalle de Solicitud (`DetalleSolicitudPage.tsx`)
- Componente `WorkflowStepper`: Barra de progreso horizontal con los 5 estados principales (`Recibido` $\rightarrow$ `En análisis` $\rightarrow$ `En desarrollo` $\rightarrow$ `En pruebas` $\rightarrow$ `Cerrado`). El estado actual debe resaltarse claramente.
- Si el estado es `Rechazado`, muestra un banner de advertencia específico.
- Pestaña o acordeón inferior de **"Trazabilidad Técnica de Integración"**:
  - Muestra el historial de `intentos_integracion` (código HTTP, fecha y mensaje de error si existió). Esto valida técnicamente ante el evaluador la robustez del sistema.

---

## 5. Configuración para Vercel (`frontend/vercel.json`)

Para evitar errores 404 al refrescar rutas en una SPA en Vercel:
```json
{
  "rewrites": [
    {
      "source": "/(.*)",
      "destination": "/index.html"
    }
  ]
}
```

---

## 6. Criterios de Aceptación (Verificables)

1. `npm install` y `npm run build` en la carpeta `frontend/` compilan sin ningún error de TypeScript ni dependencias faltantes.
2. Iniciar sesión con el Solicitante permite crear una nueva solicitud y visualizar únicamente sus propios tickets.
3. Iniciar sesión con el Coordinador permite ver la lista global de solicitudes de todos los usuarios.
4. Al hacer clic en el identificador de Jira (`SOL-X`) en la tabla o en el detalle, se abre la URL correspondiente en Jira Cloud en una nueva pestaña.
5. El diseño es responsivo y limpio, con feedback visual de carga en cada acción asíncrona.
