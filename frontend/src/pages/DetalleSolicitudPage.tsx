import { ComentariosSection } from "../components/solicitudes/ComentariosSection";
import { AdjuntosList } from "../components/solicitudes/AdjuntosList";
import { useEffect, useState } from "react";
import {
  AlertCircle,
  ArrowLeft,
  ArrowUpRight,
  Bug,
  ChevronDown,
  Clock3,
  Code2,
  LoaderCircle,
  RefreshCw,
  Sparkles,
} from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { api, errorMessage, jiraIssueUrl } from "../services/api";
import { PriorityBadge, StatusBadge } from "../components/common/StatusBadge";
import { WorkflowStepper } from "../components/solicitudes/WorkflowStepper";
import { SyncButton } from "../components/common/SyncButton";
import { useAuth } from "../context/AuthContext";
import type { SolicitudDetalle } from "../types";

function date(value: string | null): string {
  if (!value) return "Aún no registrada";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime())
    ? "Fecha no disponible"
    : parsed.toLocaleString("es-CL", {
        dateStyle: "medium",
        timeStyle: "short",
      });
}

export function DetalleSolicitudPage() {
  const { user } = useAuth();
  const { id } = useParams();
  const [item, setItem] = useState<SolicitudDetalle | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    setItem((current) => (current?.id === id ? current : null));
    if (!id) {
      setError("No encontramos la solicitud.");
      setLoading(false);
      return;
    }
    api
      .detalle(id, controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setItem(data);
      })
      .catch((failure) => {
        if (!controller.signal.aborted) setError(errorMessage(failure));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [id, revision]);

  if (loading && (!item || item.id !== id))
    return (
      <div className="empty-state" role="status">
        <LoaderCircle size={28} className="animate-spin" aria-hidden="true" />
        <h1 className="text-xl">Cargando solicitud…</h1>
      </div>
    );
  if (error || !item)
    return (
      <section className="panel empty-state">
        <AlertCircle size={30} aria-hidden="true" />
        <h1 className="text-xl">No pudimos abrir esta solicitud</h1>
        <p role="alert">{error}</p>
        <button
          className="button button-secondary"
          onClick={() => setRevision((value) => value + 1)}
        >
          Volver a intentar
        </button>
        <Link className="text-button" to="/solicitudes">
          Volver a solicitudes
        </Link>
      </section>
    );

  const integration = item.jira_integracion;
  const key = integration?.jira_issue_key;
  return (
    <>
      <Link to="/solicitudes" className="back-link">
        <ArrowLeft size={16} aria-hidden="true" />
        Volver a solicitudes
      </Link>
      <div className="page-heading detail-heading">
        <div>
          <p className="eyebrow">
            DETALLE DE SOLICITUD {key ? `· ${key}` : ""}
          </p>
          <h1>{item.titulo}</h1>
          <div className="detail-subtitle">
            <span className={`type-label type-text-${item.tipo}`}>
              {item.tipo === "incidente" ? (
                <Bug size={15} aria-hidden="true" />
              ) : (
                <Sparkles size={15} aria-hidden="true" />
              )}
              {item.tipo === "incidente" ? "Incidente" : "Mejora"}
            </span>
            <span className="separator">/</span>
            <span>{item.area}</span>
            <StatusBadge kind="business" status={item.estado_negocio} />
          </div>
        </div>
        <div className="heading-actions">
          {user?.rol === "coordinador" ? (
            <SyncButton
              solicitudId={id}
              onSynced={() => setRevision((value) => value + 1)}
              disabled={
                loading ||
                !item.jira_integracion?.jira_issue_key ||
                item.jira_integracion.estado_integracion !== "sincronizado"
              }
              label="Sincronizar ticket actual"
            />
          ) : null}
          <button
            className="button button-secondary"
            disabled={loading}
            onClick={() => setRevision((value) => value + 1)}
          >
            <RefreshCw
              size={16}
              aria-hidden="true"
              className={loading ? "animate-spin" : ""}
            />
            {loading ? "Actualizando…" : "Actualizar vista"}
          </button>
          {key ? (
            <a
              className="button button-primary"
              href={jiraIssueUrl(key)}
              target="_blank"
              rel="noopener noreferrer"
            >
              Abrir {key}
              <ArrowUpRight size={16} aria-hidden="true" />
            </a>
          ) : null}
        </div>
      </div>
      <WorkflowStepper estado={item.estado_negocio} />
      <ComentariosSection
        key={item.id}
        solicitudId={item.id}
        revision={revision}
        hasJiraTicket={Boolean(key)}
      />
      <div className="detail-layout">
        <section
          className="panel description-panel"
          aria-labelledby="description-title"
        >
          <p className="eyebrow">CONTEXTO</p>
          <h2 id="description-title">Descripción</h2>
          <p className="description-text">{item.descripcion}</p>
          <div className="author-block">
            <span className="avatar" aria-hidden="true">
              {item.autor_nombre.charAt(0).toUpperCase()}
            </span>
            <div>
              <span className="helper-text">Registrada por</span>
              <strong>{item.autor_nombre}</strong>
              <span>{item.autor_email}</span>
            </div>
            <time dateTime={item.created_at}>{date(item.created_at)}</time>
          </div>
        </section>
        <aside
          className="panel properties-panel"
          aria-labelledby="properties-title"
        >
          <h2 id="properties-title">Información general</h2>
          <dl>
            <div>
              <dt>Prioridad solicitada</dt>
              <dd>
                <PriorityBadge priority={item.prioridad_solicitada} />
              </dd>
            </div>
            <div>
              <dt>Prioridad definitiva</dt>
              <dd>
                {item.prioridad_definitiva ? (
                  <PriorityBadge priority={item.prioridad_definitiva} />
                ) : (
                  "Por definir"
                )}
              </dd>
            </div>
            <div>
              <dt>Responsable en Jira</dt>
              <dd>{item.responsable_jira || "Sin asignar"}</dd>
            </div>
            <div>
              <dt>Integración</dt>
              <dd>
                {integration ? (
                  <StatusBadge
                    kind="integration"
                    status={integration.estado_integracion}
                  />
                ) : (
                  "Sin integración"
                )}
              </dd>
            </div>
            <div>
              <dt>
                <Clock3 size={13} aria-hidden="true" />
                Última sincronización
              </dt>
              <dd>{date(integration?.ultima_sincronizacion_at ?? null)}</dd>
            </div>
          </dl>
          {integration?.estado_integracion === "fallido" ? (
            <div className="notice notice-warning">
              <AlertCircle size={17} aria-hidden="true" />
              <p>
                La solicitud está guardada. El envío a Jira requiere revisión;
                consulta la trazabilidad.
              </p>
            </div>
          ) : null}
        </aside>
      </div>
      <AdjuntosList key={item.id} solicitudId={item.id} revision={revision} />
      <details className="panel audit-panel">
        <summary>
          <span className="audit-heading">
            <Code2 size={20} aria-hidden="true" />
            <span>
              Trazabilidad Técnica de Integración
              <small>Historial reciente de comunicación con Jira Cloud</small>
            </span>
          </span>
          <span className="audit-count">
            {item.intentos_recientes.length} intentos
            <ChevronDown size={17} aria-hidden="true" />
          </span>
        </summary>
        <div className="audit-content">
          {item.intentos_recientes.length === 0 ? (
            <p className="muted">
              Todavía no hay intentos de integración registrados.
            </p>
          ) : (
            <ol>
              {item.intentos_recientes.map((attempt) => (
                <li key={attempt.id}>
                  <div className="audit-row-header">
                    <span
                      className={`badge ${attempt.http_status !== null && attempt.http_status >= 200 && attempt.http_status < 300 && !attempt.error_mensaje ? "badge-green" : "badge-red"}`}
                    >
                      {attempt.http_status
                        ? `HTTP ${attempt.http_status}`
                        : "Sin respuesta HTTP"}
                    </span>
                    <code>{attempt.operacion}</code>
                    <time dateTime={attempt.created_at}>
                      {date(attempt.created_at)}
                    </time>
                  </div>
                  {attempt.error_mensaje ? (
                    <p className="audit-error">{attempt.error_mensaje}</p>
                  ) : (
                    <p className="muted text-sm">Operación completada.</p>
                  )}
                  {attempt.payload_respuesta ? (
                    <details className="payload-details">
                      <summary>Ver respuesta de Jira</summary>
                      <pre>
                        {JSON.stringify(attempt.payload_respuesta, null, 2)}
                      </pre>
                    </details>
                  ) : null}
                </li>
              ))}
            </ol>
          )}
        </div>
      </details>
    </>
  );
}
