import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import type { EstadoNegocio } from "../../types";

const COLORS: Record<EstadoNegocio, string> = {
  Recibido: "#94a3b8",
  "En análisis": "#38bdf8",
  "En desarrollo": "#818cf8",
  "En pruebas": "#fbbf24",
  Cerrado: "#10b981",
  Rechazado: "#f87171",
};

export function StatusDonutChart({
  values,
}: {
  values: Record<EstadoNegocio, number>;
}) {
  const data = Object.entries(COLORS).map(([name, color]) => ({
    name,
    color,
    value: values[name as EstadoNegocio] ?? 0,
  }));
  const total = data.reduce((sum, item) => sum + item.value, 0);
  return (
    <section className="panel chart-panel" aria-label="Solicitudes por estado">
      <h2>Solicitudes por estado</h2>
      <p className="helper-text">Distribución del ciclo de trabajo</p>
      {total > 0 ? (
        <div className="chart-canvas" aria-hidden="true">
          <ResponsiveContainer width="100%" height="100%" minWidth={0}>
            <PieChart>
              <Pie
                data={data.filter((item) => item.value > 0)}
                dataKey="value"
                nameKey="name"
                innerRadius={60}
                outerRadius={90}
                paddingAngle={2}
                stroke="none"
                isAnimationActive={false}
              >
                {data
                  .filter((item) => item.value > 0)
                  .map((item) => (
                    <Cell key={item.name} fill={item.color} />
                  ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  background: "var(--chart-surface)",
                  color: "var(--chart-text)",
                  border: "1px solid var(--chart-grid)",
                  borderRadius: 10,
                  boxShadow: "0 6px 20px #0002",
                }}
                itemStyle={{ color: "var(--chart-text)" }}
                formatter={(value: number) => [value, "Solicitudes"]}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <p className="chart-empty">Todavía no hay solicitudes para mostrar.</p>
      )}
      <ul className="donut-legend">
        {data.map((item) => (
          <li key={item.name}>
            <span className="legend-label">
              <span
                className="legend-dot"
                style={{ background: item.color }}
                aria-hidden="true"
              />
              {item.name}
            </span>
            <span>
              <strong>{item.value}</strong>{" "}
              <small>
                ({total ? ((item.value / total) * 100).toFixed(1) : "0.0"} %)
              </small>
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
