# SPEC-002: Motor de Integración Backend (FastAPI + Jira API REST v3)

- **Versión:** 1.0.0
- **Fase:** Etapa 2 (Motor de Integración Backend)
- **Estado:** Listo para implementar
- **Responsable de Diseño:** Antigravity (Gemini)
- **Implementador:** Codex (GPT-6.1 Astra)

---

## 1. Objetivo y Contexto

Construir la API REST modular en **FastAPI** para gestionar la autenticación de usuarios por roles (`solicitante` y `coordinador`), la persistencia de solicitudes en **Supabase** y la integración asíncrona y resiliente con **Jira Cloud REST API v3**.

Garantizar que:
1. Una solicitud creada por un usuario se guarde siempre en PostgreSQL.
2. Se invoque a Jira Cloud para crear el ticket correspondiente con mapeo de campos.
3. Si la conexión con Jira falla o sufre timeout, la solicitud en base de datos **no se pierde**; pasa a `estado_integracion = 'fallido'` (habiendo iniciado en `pendiente`) y se audita el fallo con código HTTP y mensaje en `intentos_integracion`.
4. La clave de correlación `[CORRELATION_ID: <uuid>]` se inyecte en la descripción del ticket en Jira para prevenir duplicados.

---

## 2. Archivos a Crear / Modificar

```text
backend/
├── requirements.txt                      (Modificar: agregar fastapi, uvicorn, httpx, python-jose, pytest)
├── app/
│   ├── __init__.py
│   ├── main.py                           (Entrypoint FastAPI, CORS, inclusión de routers)
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py                     (Pydantic Settings para .env)
│   │   ├── database.py                   (AsyncEngine, AsyncSession, get_db)
│   │   └── security.py                   (create_access_token, verify_password, get_password_hash)
│   ├── models/
│   │   ├── __init__.py
│   │   ├── usuario.py                    (Modelo SQLAlchemy Usuarios)
│   │   ├── solicitud.py                  (Modelo SQLAlchemy Solicitudes)
│   │   └── integracion.py                (Modelos JiraIntegracion e IntentoIntegracion)
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── auth.py                       (Token, LoginRequest, UserResponse)
│   │   ├── solicitud.py                  (SolicitudCreate, SolicitudResponse, SolicitudDetailResponse)
│   │   └── jira.py                       (JiraIssueResponse, JiraSyncResponse)
│   ├── services/
│   │   ├── __init__.py
│   │   └── jira_client.py                (Cliente HTTP asíncrono httpx contra Jira Cloud v3)
│   └── api/
│       ├── __init__.py
│       ├── deps.py                       (get_current_user, require_role)
│       └── v1/
│           ├── __init__.py
│           ├── auth.py                   (POST /api/v1/auth/login, GET /api/v1/auth/me)
│           └── solicitudes.py            (POST /api/v1/solicitudes, GET /api/v1/solicitudes, GET /api/v1/solicitudes/{id})
└── tests/
    ├── __init__.py
    ├── conftest.py                       (Fixtures async de BD y cliente de prueba)
    └── test_solicitudes_jira.py          (Pruebas unitarias de creación y simulación de fallos Jira)
```

---

## 3. Contratos de Datos y Esquemas Pydantic

### 3.1. Autenticación (`schemas/auth.py`)
```python
class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: UUID
    rol: str
    nombre: str

class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    nombre: str
    rol: str
```

### 3.2. Solicitudes (`schemas/solicitud.py`)
```python
class SolicitudCreate(BaseModel):
    titulo: str = Field(..., min_length=5, max_length=200)
    descripcion: str = Field(..., min_length=10)
    tipo: Literal["incidente", "mejora"]
    area: str = Field(..., min_length=2, max_length=100)
    prioridad_solicitada: Literal["baja", "media", "alta", "urgente"] = "media"

class JiraIntegracionSchema(BaseModel):
    jira_issue_key: Optional[str]
    estado_integracion: str
    ultima_sincronizacion_at: Optional[datetime]

class SolicitudResponse(BaseModel):
    id: UUID
    titulo: str
    tipo: str
    area: str
    prioridad_solicitada: str
    prioridad_definitiva: Optional[str]
    estado_negocio: str
    responsable_jira: Optional[str]
    created_at: datetime
    jira_integracion: Optional[JiraIntegracionSchema]

class SolicitudDetailResponse(SolicitudResponse):
    descripcion: str
    autor_email: str
    autor_nombre: str
    intentos_recientes: List[dict] = []
```

---

## 4. Mapeo y Lógica de Integración con Jira Cloud (`services/jira_client.py`)

### 4.1. Mapeo de Campos
- **Tipo de Incidencia:**
  - `incidente` $\rightarrow$ `"Error"` (en Jira Cloud español).
  - `mejora` $\rightarrow$ `"Tarea"` (en Jira Cloud español).
- **Prioridad:**
  - `baja` $\rightarrow$ `"Lowest"`
  - `media` $\rightarrow$ `"Medium"`
  - `alta` $\rightarrow$ `"High"`
  - `urgente` $\rightarrow$ `"Highest"`
- **Formato Atlassian Document Format (ADF) para Descripción:**  
  La API v3 de Jira requiere la descripción en formato ADF JSON:
  ```json
  {
    "type": "doc",
    "version": 1,
    "content": [
      {
        "type": "paragraph",
        "content": [
          { "type": "text", "text": "Descripción: {descripcion}\nÁrea: {area}\nPrioridad solicitada: {prioridad}\n\n[CORRELATION_ID: {solicitud_id}]" }
        ]
      }
    ]
  }
  ```

### 4.2. Algoritmo de Creación de Solicitud (`POST /api/v1/solicitudes`)
1. **Validación:** Validar payload de entrada y usuario autenticado.
2. **Persistencia Local (Transacción 1):**
   - Insertar registro en tabla `solicitudes` con `autor_id = current_user.id`, `estado_negocio = 'Recibido'`.
   - Insertar registro inicial en `jira_integraciones` con `solicitud_id`, `estado_integracion = 'pendiente'`.
   - Commit en base de datos.
3. **Llamada a Jira Cloud (Asíncrona via HTTPX):**
   - Construir payload para `POST /rest/api/3/issue`.
   - Enviar con Basic Auth (`email` + `token`), timeout de 10 segundos.
4. **Manejo de Respuesta:**
   - **Caso Éxito (HTTP 201 Created):**
     - Extraer `id` y `key` del ticket Jira (ej. `SOL-12`).
     - Actualizar `jira_integraciones`: `jira_issue_id = id`, `jira_issue_key = key`, `estado_integracion = 'sincronizado'`, `ultima_sincronizacion_at = NOW()`.
     - Insertar en `intentos_integracion`: `operacion = 'CREATE_ISSUE'`, `http_status = 201`, `payload_respuesta = resp.json()`.
   - **Caso Falla (HTTP 4xx / 5xx o TimeoutException):**
     - Actualizar `jira_integraciones`: `estado_integracion = 'fallido'`.
     - Insertar en `intentos_integracion`: `operacion = 'CREATE_ISSUE'`, `http_status = status_code o 0`, `error_mensaje = str(exc)`, `payload_respuesta = body_error`.
     - **No revertir la solicitud:** La solicitud sigue existiendo para el usuario en el portal; el coordinador podrá reintentar el envío.
5. **Retorno:** Devolver HTTP 201 con la `SolicitudResponse` y el estado de integración resultante.

---

## 5. Reglas de Autorización por Endpoint

| Endpoint | Rol Permitido | Comportamiento |
| :--- | :--- | :--- |
| `POST /api/v1/auth/login` | Público | Genera JWT firmado con `JWT_SECRET_KEY` (expira en 8 horas). |
| `GET /api/v1/auth/me` | Cualquier autenticado | Devuelve datos del usuario en sesión. |
| `POST /api/v1/solicitudes` | `solicitante` o `coordinador` | Crea solicitud y despacha llamada a Jira. |
| `GET /api/v1/solicitudes` | Ambos | **Filtro estricto:** Si `rol == 'solicitante'`, devuelve **únicamente** solicitudes donde `autor_id == current_user.id`. Si `rol == 'coordinador'`, devuelve todas. |
| `GET /api/v1/solicitudes/{id}` | Ambos | Si es `solicitante` y no es el autor $\rightarrow$ `HTTP 403 Forbidden`. |

---

## 6. Criterios de Aceptación (Verificables)

1. **Autenticación:**
   - `POST /api/v1/auth/login` con `solicitante@empresa.com` / `Solicitante123!` devuelve un JWT válido con `rol: "solicitante"`.
2. **Creación con Jira Real:**
   - Enviar una solicitud válida con token de autenticación crea el registro en Supabase y **un ticket visible en el tablero Kanban de Jira Cloud** (`SOL-X`).
   - El ticket en Jira muestra el tipo correcto (`Error` para incidentes, `Tarea` para mejoras) y la marca `[CORRELATION_ID: ...]`.
3. **Resiliencia ante Fallo:**
   - Si se simulan credenciales inválidas de Jira o timeout, la API no retorna error 500 al cliente: persiste la solicitud en Supabase con `estado_integracion = 'fallido'` y registra el error en `intentos_integracion`.
4. **Permisos y Filtros:**
   - Un solicitante no puede ver las solicitudes de otros usuarios en `GET /api/v1/solicitudes`.
