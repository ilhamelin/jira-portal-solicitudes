import { useId } from "react";

export function BarChartSimple({
  title,
  subtitle,
  items,
  total,
}: {
  title: string;
  subtitle: string;
  items: { label: string; value: number }[];
  total: number;
}) {
  const id = useId();
  return (
    <section className="panel chart-panel" aria-labelledby={id}>
      <h2 id={id}>{title}</h2>
      <p className="helper-text">{subtitle}</p>
      {items.length ? (
        <ul className="chart-bars">
          {items.map((item) => {
            const percentage =
              total > 0
                ? Math.min(100, Math.max(0, (item.value / total) * 100))
                : 0;
            return (
              <li key={item.label}>
                <div className="chart-row">
                  <span>{item.label}</span>
                  <span>
                    <strong>{item.value}</strong>
                    <small>{percentage.toFixed(1)} %</small>
                  </span>
                </div>
                <div
                  className="chart-track"
                  role="meter"
                  aria-label={item.label}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={Number(percentage.toFixed(1))}
                  aria-valuetext={`${item.value} solicitudes, ${percentage.toFixed(1)} por ciento`}
                >
                  <span style={{ width: `${percentage}%` }} />
                </div>
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="chart-empty">Todavía no hay solicitudes para mostrar.</p>
      )}
    </section>
  );
}
