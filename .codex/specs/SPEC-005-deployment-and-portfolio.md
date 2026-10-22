# SPEC-005: Despliegue en la Nube (Vercel), Contenerización (Docker Compose) y Documentación de Portafolio

- **Versión:** 1.0.0
- **Fase:** Etapa 5 (Despliegue y Portafolio)
- **Estado:** Listo para implementar
- **Responsable de Diseño:** Antigravity (Gemini)
- **Implementador:** Codex / Antigravity

---

## 1. Objetivo y Contexto

Culminar el proyecto preparando todos los entregables profesionales exigidos para el portafolio de la vacante **Desarrollador Junior Integraciones con JIRA**:
1. **Contenerización Local:** `backend/Dockerfile` y `docker-compose.yml` para levantar la solución completa en cualquier máquina con `docker compose up`.
2. **Control de Versiones Seguro:** Inicialización del repositorio Git, verificación de exclusión de secretos en `.gitignore` y commit semántico estructurado.
3. **Despliegue en Vercel:** Configuración de compilación para el frontend (`dist`) con variables de entorno de producción.
4. **README Técnico y Diagramas:** Documentación en GitHub con diagramas Mermaid de arquitectura y flujo, credenciales demo e instrucciones de despliegue.

---

## 2. Archivos a Crear / Actualizar

```text
jira-portal-solicitudes/
├── docker-compose.yml            (Orquestación de backend y frontend)
├── backend/
│   └── Dockerfile                (Contenedor optimizado de FastAPI)
├── frontend/
│   ├── Dockerfile                (Contenedor de desarrollo/producción de Vite)
│   └── .dockerignore
└── README.md                     (Documentación completa con badges, diagramas y guía)
```

---

## 3. Especificación de Contenedores

### 3.1. `backend/Dockerfile`
- Imagen base: `python:3.11-slim`
- Instala dependencias del sistema mínimas (`gcc`, `libpq-dev`).
- Copia `requirements.txt` e instala dependencias con pip.
- Copia `app/` y expone el puerto `8000`.
- Comando de arranque: `CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]`

### 3.2. `docker-compose.yml`
- Servicios:
  - `backend`: Build desde `./backend`, mapeo de puerto `8000:8000`, carga de archivo `.env`.
  - `frontend`: Build desde `./frontend`, mapeo de puerto `5173:5173`, variable `VITE_API_URL=http://localhost:8000/api/v1`.

---

## 4. Guía de Despliegue en Vercel

1. **Subir a GitHub:**
   - Crear un repositorio público en GitHub (ej. `jira-portal-solicitudes`).
   - Vincular el remoto y hacer `git push -u origin main`.
2. **Importar en Vercel:**
   - En el dashboard de Vercel ([vercel.com](https://vercel.com)), hacer clic en **"Add New..." $\rightarrow$ "Project"**.
   - Seleccionar el repositorio de GitHub.
   - **Root Directory:** Indicar `frontend`.
   - **Framework Preset:** Seleccionar `Vite`.
   - **Environment Variables:** Añadir `VITE_API_URL` apuntando a la URL del backend.
   - Clic en **Deploy**.

---

## 5. Criterios de Aceptación (Verificables)

1. El archivo `.env` **nunca** se agrega al historial de Git (`git status` muestra que está ignorado).
2. `docker compose config` valida la sintaxis de los contenedores sin errores.
3. El `README.md` describe la solución de forma clara, con capturas o referencias a Jira Cloud y Supabase, permitiendo a cualquier reclutador entender el problema y la solución en menos de 2 minutos.
