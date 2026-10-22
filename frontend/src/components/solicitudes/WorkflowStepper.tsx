import { AlertTriangle, Check, X } from "lucide-react";
import type { EstadoNegocio } from "../../types";

const STEPS: EstadoNegocio[] = [
  "Recibido",
  "En análisis",
  "En desarrollo",
  "En pruebas",
  "Cerrado",
];

export function WorkflowStepper({ estado }: { estado: EstadoNegocio }) {
  const rejected = estado === "Rechazado";
  const active = rejected ? 1 : STEPS.indexOf(estado);
  return (
    <section className="panel workflow-panel" aria-labelledby="workflow-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">SEGUIMIENTO</p>
          <h2 id="workflow-title">Ciclo de la solicitud</h2>
        </div>
        <span className="muted text-sm">Gestionado en Jira</span>
      </div>
      {rejected ? (
        <div className="notice notice-warning" role="status">
          <AlertTriangle size={19} aria-hidden="true" />
          <div>
            <strong>Solicitud rechazada</strong>
            <p>El flujo terminó durante la etapa de análisis.</p>
          </div>
        </div>
      ) : null}
      <div
        className="stepper-scroll"
        tabIndex={0}
        role="region"
        aria-label="Etapas del flujo de Jira"
      >
        <ol className="stepper">
          {STEPS.map((step, index) => {
            const done =
              index < active || (estado === "Cerrado" && index === active);
            const current = index === active;
            return (
              <li
                key={step}
                className={`${done ? "step-done" : ""} ${current ? "step-current" : ""} ${rejected && current ? "step-rejected" : ""}`}
                aria-current={current && !rejected ? "step" : undefined}
              >
                <span className="step-node" aria-hidden="true">
                  {rejected && current ? (
                    <X size={16} />
                  ) : done ? (
                    <Check size={16} />
                  ) : (
                    String(index + 1).padStart(2, "0")
                  )}
                </span>
                <span className="step-name">{step}</span>
                <span className="step-caption">
                  {rejected && current
                    ? "Rechazada"
                    : current
                      ? estado === "Cerrado"
                        ? "Finalizada"
                        : "Estado actual"
                      : done
                        ? "Completada"
                        : rejected
                          ? "No alcanzada"
                          : "Siguiente etapa"}
                </span>
              </li>
            );
          })}
        </ol>
      </div>
      <p className="helper-text">
        El portal refleja el estado registrado en Jira Cloud.
      </p>
    </section>
  );
}
