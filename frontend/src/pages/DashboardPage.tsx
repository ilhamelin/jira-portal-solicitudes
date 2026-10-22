import { useEffect, useState } from "react";
import {
  AlertCircle,
  AlertTriangle,
  Clock3,
  Layers3,
  RefreshCw,
  Target,
} from "lucide-react";
import { api, errorMessage } from "../services/api";
import type { DashboardMetrics } from "../types";
import { SyncButton } from "../components/common/SyncButton";
import { BarChartSimple } from "../components/dashboard/BarChartSimple";
import { MetricCard } from "../components/dashboard/MetricCard";
import { StalledAlertCard } from "../components/dashboard/StalledAlertCard";

import { StatusDonutChart } from "../components/dashboard/StatusDonutChart";
import { AreaBarChart } from "../components/dashboard/AreaBarChart";
import { MetricSkeleton } from "../components/dashboard/MetricSkeleton";

const TYPE_LABELS: Record<string, string> = {
  incidente: "Incidentes",
  mejora: "Mejoras",
};
const PRIORITY_LABELS: Record<string, string> = {
  baja: "Baja",
  media: "Media",
  alta: "Alta",
  urgente: "Urgente",
};
function chartItems(
  values: Record<string, number>,
  labels: Record<string, string> = {},
) {
  return Object.entries(values).map(([key, value]) => ({
    label: labels[key] ?? key,
    value,
  }));
}

export function DashboardPage() {
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    api
      .getDashboardMetrics(controller.signal)
      .then((value) => {
        if (!controller.signal.aborted) setMetrics(value);
      })
      .catch((failure) => {
        if (!controller.signal.aborted) setError(errorMessage(failure));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [revision]);
  const refresh = () => setRevision((value) => value + 1);
  const lastSync = metrics?.ultima_sincronizacion_general
    ? new Date(metrics.ultima_sincronizacion_general)
    : null;

  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">VISIÓN DE GESTIÓN</p>
          <h1>Dashboard del equipo</h1>
          <p className="page-description">
            El estado de las solicitudes, las prioridades y lo que requiere
            atención.
          </p>
        </div>
        <div className="heading-actions">
          <button
            className="button button-quiet"
            onClick={refresh}
            disabled={loading}
          >
            <RefreshCw
              size={16}
              className={loading ? "animate-spin" : ""}
              aria-hidden="true"
            />
            Actualizar métricas
          </button>
          <SyncButton onSynced={refresh} disabled={loading} />
        </div>
      </div>
      {error ? (
        <div className="notice notice-error" role="alert">
          <AlertCircle size={20} aria-hidden="true" />
          <div>
            {error}
            <button
              className="text-button block"
              onClick={refresh}
              disabled={loading}
            >
              Volver a intentar
            </button>
          </div>
        </div>
      ) : null}
      {loading ? <MetricSkeleton /> : null}
      {metrics ? (
        <div className="dashboard-content" aria-busy={loading}>
          {!loading ? (
            <section
              className="metric-grid"
              aria-label="Indicadores de gestión"
            >
              <MetricCard
                label="Total Solicitudes"
                value={metrics.total_solicitudes}
                caption="Todos los registros del portal"
                icon={Layers3}
              />
              <MetricCard
                label="Tasa de Resolución"
                value={`${metrics.tasa_resolucion_pct.toFixed(1)} %`}
                caption="Solicitudes cerradas sobre el total"
                icon={Target}
                progress={metrics.tasa_resolucion_pct}
              />
              <MetricCard
                label="Solicitudes Estancadas"
                value={metrics.solicitudes_estancadas}
                caption="Activas sin cambios por más de 5 días"
                icon={AlertTriangle}
                warning={metrics.solicitudes_estancadas > 0}
              />
              <MetricCard
                label="Última Sincronización"
                value={
                  lastSync
                    ? lastSync.toLocaleTimeString("es-CL", {
                        hour: "2-digit",
                        minute: "2-digit",
                      })
                    : "Sin registros"
                }
                caption={
                  lastSync
                    ? lastSync.toLocaleDateString("es-CL", {
                        dateStyle: "medium",
                      })
                    : "Todavía no hay una sincronización registrada"
                }
                icon={Clock3}
              />
            </section>
          ) : null}
          <StalledAlertCard count={metrics.solicitudes_estancadas} />
          <div className="chart-grid">
            <StatusDonutChart values={metrics.por_estado} />
            <AreaBarChart values={metrics.por_area} />
            <BarChartSimple
              title="Incidentes y mejoras"
              subtitle="Tipo de solicitudes registradas"
              items={chartItems(metrics.por_tipo, TYPE_LABELS)}
              total={metrics.total_solicitudes}
            />
            <BarChartSimple
              title="Distribución por prioridad"
              subtitle="Prioridad definitiva o, si falta, la solicitada"
              items={chartItems(metrics.por_prioridad, PRIORITY_LABELS)}
              total={metrics.total_solicitudes}
            />
          </div>
          <p className="page-footnote">
            La sincronización consulta Jira Cloud. Las métricas se calculan
            desde los registros guardados en el portal.
          </p>
        </div>
      ) : null}
    </>
  );
}
