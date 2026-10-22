import { useId } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export function AreaBarChart({ values }: { values: Record<string, number> }) {
  const gradient = useId().replace(/:/g, "");
  const data = Object.entries(values).map(([name, value]) => ({ name, value }));
  const hasData = data.some((item) => item.value > 0);
  return (
    <section className="panel chart-panel" aria-label="Solicitudes por área">
      <h2>Solicitudes por área</h2>
      <p className="helper-text">Participación de cada equipo</p>
      {hasData ? (
        <>
          <div className="chart-canvas area-chart" aria-hidden="true">
            <ResponsiveContainer width="100%" height="100%" minWidth={0}>
              <BarChart
                data={data}
                margin={{ top: 12, right: 12, bottom: 45, left: -20 }}
              >
                <defs>
                  <linearGradient id={gradient} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#34d399" />
                    <stop offset="100%" stopColor="#059669" />
                  </linearGradient>
                </defs>
                <CartesianGrid
                  strokeDasharray="3 3"
                  vertical={false}
                  stroke="var(--chart-grid)"
                />
                <XAxis
                  dataKey="name"
                  interval={0}
                  angle={-30}
                  textAnchor="end"
                  height={65}
                  tick={{ fill: "var(--chart-text)", fontSize: 10 }}
                  tickLine={false}
                />
                <YAxis
                  allowDecimals={false}
                  tick={{ fill: "var(--chart-text)", fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  cursor={{ fill: "var(--chart-hover)" }}
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
                <Bar
                  dataKey="value"
                  fill={`url(#${gradient})`}
                  radius={[6, 6, 0, 0]}
                  maxBarSize={52}
                  isAnimationActive={false}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <ul className="sr-only">
            {data.map((item) => (
              <li key={item.name}>
                {item.name}: {item.value} solicitudes
              </li>
            ))}
          </ul>
        </>
      ) : (
        <p className="chart-empty">Todavía no hay solicitudes para mostrar.</p>
      )}
    </section>
  );
}
