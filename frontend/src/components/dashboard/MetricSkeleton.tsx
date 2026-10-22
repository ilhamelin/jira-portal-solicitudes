export function MetricSkeleton() {
  return (
    <section
      className="metric-grid"
      role="status"
      aria-label="Cargando métricas"
      aria-busy="true"
    >
      <span className="sr-only">Cargando métricas del equipo…</span>
      {Array.from({ length: 4 }, (_, index) => (
        <div className="panel metric-card" key={index} aria-hidden="true">
          <div className="skeleton-block animate-pulse bg-slate-200 dark:bg-slate-800" />
          <div className="skeleton-block skeleton-value animate-pulse bg-slate-200 dark:bg-slate-800" />
          <div className="skeleton-block animate-pulse bg-slate-200 dark:bg-slate-800" />
        </div>
      ))}
    </section>
  );
}
