import { AlertTriangle, Check, Clock3, LoaderCircle } from "lucide-react";
import type {
  EstadoIntegracion,
  EstadoNegocio,
  PrioridadTipo,
} from "../../types";

const businessColors: Record<EstadoNegocio, string> = {
  Recibido: "badge-neutral",
  "En análisis": "badge-blue",
  "En desarrollo": "badge-violet",
  "En pruebas": "badge-amber",
  Cerrado: "badge-green",
  Rechazado: "badge-red",
};
const integration = {
  pendiente: { label: "Pendiente", color: "badge-amber", Icon: Clock3 },
  sincronizado: { label: "Sincronizado", color: "badge-green", Icon: Check },
  fallido: { label: "Fallido", color: "badge-red", Icon: AlertTriangle },
  reintentando: {
    label: "Reintentando",
    color: "badge-blue",
    Icon: LoaderCircle,
  },
};

export function StatusBadge(
  props:
    | { kind: "business"; status: EstadoNegocio }
    | { kind: "integration"; status: EstadoIntegracion },
) {
  if (props.kind === "business")
    return (
      <span
        className={`badge ${businessColors[props.status] || "badge-neutral"}`}
      >
        <span className="badge-dot" />
        {props.status}
      </span>
    );
  const item = integration[props.status];
  if (!item) return <span className="badge badge-neutral">{props.status}</span>;
  const { Icon } = item;
  return (
    <span className={`badge ${item.color}`}>
      <Icon
        size={13}
        aria-hidden="true"
        className={props.status === "reintentando" ? "animate-spin" : ""}
      />
      {item.label}
    </span>
  );
}

const priorityLabels: Record<PrioridadTipo, string> = {
  baja: "Baja",
  media: "Media",
  alta: "Alta",
  urgente: "Urgente",
};
export function PriorityBadge({ priority }: { priority: PrioridadTipo }) {
  return (
    <span className={`priority priority-${priority}`}>
      <span aria-hidden="true">
        {priority === "urgente"
          ? "↑↑"
          : priority === "alta"
            ? "↑"
            : priority === "baja"
              ? "↓"
              : "−"}
      </span>
      {priorityLabels[priority]}
    </span>
  );
}
