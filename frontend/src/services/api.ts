import { clearToken, getToken } from "./auth";
import type {
  AuthResponse,
  BulkSyncResponse,
  DashboardMetrics,
  Solicitud,
  SolicitudCreateInput,
  SolicitudDetalle,
  SyncResult,
  Usuario,
} from "../types";

const API_URL = (
  import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1"
).replace(/\/+$/, "");

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public fields: Record<string, string> = {},
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  authenticated = true,
): Promise<T> {
  const token = authenticated ? getToken() : null;
  const headers = new Headers(options.headers);
  headers.set("Accept", "application/json");
  if (options.body) headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, { ...options, headers });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError")
      throw error;
    throw new ApiError(
      "No se pudo conectar con el portal. Comprueba tu conexión e inténtalo nuevamente.",
      0,
    );
  }
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    if (response.status === 401 && token) clearToken(token);
    const fields: Record<string, string> = {};
    let message =
      response.status === 403
        ? "No tienes permiso para esta operación."
        : response.status === 404
          ? "No encontramos la solicitud que buscas."
          : response.status === 401
            ? authenticated
              ? "Tu sesión terminó. Vuelve a ingresar."
              : "Email o contraseña incorrectos."
            : "No fue posible completar la operación. Inténtalo nuevamente.";
    if (
      (response.status === 400 || response.status === 502) &&
      typeof body === "object" &&
      body !== null &&
      "detail" in body &&
      typeof body.detail === "string"
    )
      message = body.detail;
    if (
      response.status === 422 &&
      typeof body === "object" &&
      body !== null &&
      "detail" in body &&
      Array.isArray(body.detail)
    ) {
      message = "Revisa los campos del formulario.";
      for (const issue of body.detail) {
        if (
          typeof issue === "object" &&
          issue !== null &&
          Array.isArray(issue.loc)
        ) {
          fields[String(issue.loc.at(-1))] = "Revisa el valor de este campo.";
        }
      }
    }
    throw new ApiError(message, response.status, fields);
  }
  if (body === null)
    throw new ApiError(
      "El servidor devolvió una respuesta inesperada.",
      response.status,
    );
  return body as T;
}

export const api = {
  login: (email: string, password: string) =>
    request<AuthResponse>(
      "/auth/login",
      { method: "POST", body: JSON.stringify({ email, password }) },
      false,
    ),
  me: (signal?: AbortSignal) => request<Usuario>("/auth/me", { signal }),
  solicitudes: (offset = 0, signal?: AbortSignal) =>
    request<Solicitud[]>(`/solicitudes?limit=50&offset=${offset}`, { signal }),
  detalle: (id: string, signal?: AbortSignal) =>
    request<SolicitudDetalle>(`/solicitudes/${encodeURIComponent(id)}`, {
      signal,
    }),
  crear: (input: SolicitudCreateInput) =>
    request<Solicitud>("/solicitudes", {
      method: "POST",
      body: JSON.stringify(input),
    }),
  syncSolicitud: (id: string) =>
    request<SyncResult>(`/solicitudes/${encodeURIComponent(id)}/sync`, {
      method: "POST",
    }),
  syncAllJira: () =>
    request<BulkSyncResponse>("/jira/sync", { method: "POST" }),
  getDashboardMetrics: (signal?: AbortSignal) =>
    request<DashboardMetrics>("/dashboard/metrics", { signal }),
};

export const jiraIssueUrl = (key: string) =>
  `https://portal-solicitudes-dev.atlassian.net/browse/${encodeURIComponent(key)}`;

export function errorMessage(error: unknown): string {
  return error instanceof Error
    ? error.message
    : "Ocurrió un error inesperado. Inténtalo nuevamente.";
}
