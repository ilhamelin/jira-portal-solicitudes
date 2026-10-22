export type RolUsuario = "solicitante" | "coordinador";
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
export type TipoSolicitud = "incidente" | "mejora";
export type PrioridadTipo = "baja" | "media" | "alta" | "urgente";
export type EstadoNegocio =
  | "Recibido"
  | "En análisis"
  | "En desarrollo"
  | "En pruebas"
  | "Cerrado"
  | "Rechazado";
export type EstadoIntegracion =
  "pendiente" | "sincronizado" | "fallido" | "reintentando";
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
