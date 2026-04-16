import { SurfaceCard } from "./SurfaceCard";

type MetricCardProps = {
  label: string;
  value: number | string;
  tone?: "default" | "success" | "danger" | "warning" | "info";
};

export function MetricCard({ label, value, tone = "default" }: MetricCardProps) {
  const toneColor =
    tone === "success"
      ? "var(--success)"
      : tone === "danger"
        ? "var(--danger)"
        : tone === "warning"
          ? "var(--warning)"
          : tone === "info"
            ? "var(--info)"
            : "var(--text-primary)";

  return (
    <SurfaceCard>
      <div className="text-[0.75rem] text-[var(--text-tertiary)] mb-[var(--space-1)]">{label}</div>
      <div className="text-2xl font-semibold" style={{ color: toneColor }}>
        {value}
      </div>
    </SurfaceCard>
  );
}
