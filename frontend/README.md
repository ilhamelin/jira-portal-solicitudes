# Portal web — SPEC-003

Desde `frontend/`:

```sh
npm install
# Copiar .env.example a .env.local y ajustar VITE_API_URL si es necesario.
npm run dev
npm run build
```

El backend debe estar disponible en `http://localhost:8000` para el entorno local.
La API base incluye `/api/v1`; el cliente añade rutas como `/auth/login` y
`/solicitudes`. Los filtros actúan sobre los registros cargados; el botón
«Cargar más solicitudes» consulta la siguiente página del backend.

La sesión guarda únicamente el token en localStorage y obtiene el usuario y su
rol desde `/auth/me`. Una respuesta 401 elimina la sesión y vuelve al acceso.
La autorización de los registros pertenece al backend.

## Vercel

- Seleccionar `frontend` como **Root Directory**, con framework **Vite**.
- Build Command: `npm run build`. Output Directory: `dist`.
- Definir `VITE_API_URL` con la URL HTTPS del backend, incluyendo `/api/v1`,
  antes de compilar/desplegar. Las variables `VITE_*` son públicas; no agregar
  secretos de JWT, Jira ni PostgreSQL.
- Incluir el origen del frontend en `ALLOWED_ORIGINS` del backend.
- `vercel.json` contiene la reescritura SPA para rutas de listado y detalle.

Los enlaces Jira usan la instancia indicada en la especificación:
`https://portal-solicitudes-dev.atlassian.net`.

El frontend muestra el estado almacenado por el backend. «Actualizar vista»
vuelve a consultar la API. El coordinador puede usar «Sincronizar con Jira»
para consultar los tickets activos, o sincronizar un ticket desde su detalle.
La ruta `/dashboard` y sus métricas están reservadas al coordinador.
La sincronización periódica y el reintento de creaciones fallidas pertenecen
a una etapa posterior; esta entrega realiza sincronización manual de tickets
ya vinculados. Los fallos parciales se notifican y quedan en la auditoría.
