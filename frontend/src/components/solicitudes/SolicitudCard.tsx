import { ArrowUpRight, Bug, ChevronRight, Sparkles } from "lucide-react";
import { Link } from "react-router-dom";
import { jiraIssueUrl } from "../../services/api";
import type { Solicitud } from "../../types";
import { PriorityBadge, StatusBadge } from "../common/StatusBadge";

export function SolicitudCard({ solicitud }: { solicitud: Solicitud }) {
  const issueKey = solicitud.jira_integracion?.jira_issue_key;
  return (
    <article className="request-row">
      <div className="request-title">
        <span className={`type-icon type-${solicitud.tipo}`}>
          {solicitud.tipo === "incidente" ? (
            <Bug size={17} aria-hidden="true" />
          ) : (
            <Sparkles size={17} aria-hidden="true" />
          )}
        </span>
        <div>
          <Link
            to={`/solicitudes/${solicitud.id}`}
            className="request-title-link"
          >
            {solicitud.titulo}
          </Link>
          <span className="request-date">
            {new Date(solicitud.created_at).toLocaleDateString("es-CL", {
              day: "numeric",
              month: "short",
              year: "numeric",
            })}
          </span>
        </div>
      </div>
      <span className="row-type">
        {solicitud.tipo === "incidente" ? "Incidente" : "Mejora"}
      </span>
      <span className="row-area">{solicitud.area}</span>
      <PriorityBadge
        priority={
          solicitud.prioridad_definitiva ?? solicitud.prioridad_solicitada
        }
      />
      <StatusBadge kind="business" status={solicitud.estado_negocio} />
      <div className="row-jira">
        {issueKey ? (
          <a
            href={jiraIssueUrl(issueKey)}
            target="_blank"
            rel="noopener noreferrer"
            className="jira-link"
            aria-label={`Abrir ${issueKey} en Jira, nueva pestaña`}
          >
            {issueKey}
            <ArrowUpRight size={13} aria-hidden="true" />
          </a>
        ) : (
          <span className="muted">Sin ticket</span>
        )}
        {solicitud.jira_integracion ? (
          <StatusBadge
            kind="integration"
            status={solicitud.jira_integracion.estado_integracion}
          />
        ) : (
          <span className="muted">Sin integración</span>
        )}
      </div>
      <Link
        to={`/solicitudes/${solicitud.id}`}
        className="row-arrow"
        aria-label={`Ver detalle de ${solicitud.titulo}`}
      >
        <ChevronRight size={18} />
      </Link>
    </article>
  );
}
