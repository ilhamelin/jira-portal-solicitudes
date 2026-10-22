export function SkeletonTable() {
  return (
    <div
      className="skeleton-table"
      role="status"
      aria-label="Cargando solicitudes"
      aria-busy="true"
    >
      <span className="sr-only">Cargando solicitudes…</span>
      <div aria-hidden="true">
        {Array.from({ length: 5 }, (_, row) => (
          <div className="skeleton-row" key={row}>
            {Array.from({ length: 5 }, (_, col) => (
              <div
                className="skeleton-block animate-pulse bg-slate-200 dark:bg-slate-800"
                key={col}
              />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
