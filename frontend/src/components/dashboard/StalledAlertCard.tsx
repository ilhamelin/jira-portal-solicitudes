import { AlertTriangle, ArrowRight, CheckCircle2 } from "lucide-react";
import { Link } from "react-router-dom";

export function StalledAlertCard({ count }: { count: number }) {
  return (
    <aside
      className={`stalled-alert ${count > 0 ? "stalled-alert-warning" : ""}`}
      role="status"
    >
      {count > 0 ? (
        <AlertTriangle size={23} aria-hidden="true" />
      ) : (
        <CheckCircle2 size={23} aria-hidden="true" />
      )}
      <div>
        <h2>
          {count > 0
            ? `${count} ${count === 1 ? "solicitud necesita" : "solicitudes necesitan"} atención`
            : "Sin solicitudes estancadas"}
        </h2>
        <p>
          {count > 0
            ? "Hay solicitudes activas sin cambios de estado o responsable durante más de cinco días."
            : "No hay solicitudes activas sin cambios durante más de cinco días."}
        </p>
      </div>
      {count > 0 ? (
        <Link className="text-button" to="/solicitudes">
          Revisar solicitudes
          <ArrowRight size={15} aria-hidden="true" />
        </Link>
      ) : null}
    </aside>
  );
}
