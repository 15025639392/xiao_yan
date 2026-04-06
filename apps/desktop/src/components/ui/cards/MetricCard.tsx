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
      <div style={{ fontSize: "0.75rem", color: "var(--text-tertiary)", marginBottom: "var(--space-1)" }}>{label}</div>
      <div style={{ fontSize: "1.5rem", fontWeight: 600, color: toneColor }}>{value}</div>
    </SurfaceCard>
  );
}
