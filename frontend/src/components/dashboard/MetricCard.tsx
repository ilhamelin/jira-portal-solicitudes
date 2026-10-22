import type { LucideIcon } from "lucide-react";

export function MetricCard({
  label,
  value,
  caption,
  icon: Icon,
  progress,
  warning = false,
}: {
  label: string;
  value: string | number;
  caption: string;
  icon: LucideIcon;
  progress?: number;
  warning?: boolean;
}) {
  return (
    <article
      className={`panel metric-card ${warning ? "metric-card-warning" : ""}`}
    >
      <div className="metric-label">
        <span>{label}</span>
        <span className="metric-icon">
          <Icon size={19} aria-hidden="true" />
        </span>
      </div>
      <p className="metric-value">{value}</p>
      {progress !== undefined ? (
        <div
          className="metric-progress"
          role="progressbar"
          aria-label={label}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={progress}
        >
          <span style={{ width: `${Math.min(100, Math.max(0, progress))}%` }} />
        </div>
      ) : null}
      <p className="metric-caption">{caption}</p>
    </article>
  );
}
