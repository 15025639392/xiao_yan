import type { CSSProperties, ReactNode } from "react";

type InlineAlertTone = "danger" | "warning" | "info" | "success";

type InlineAlertProps = {
  tone?: InlineAlertTone;
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
};

function resolveToneVars(tone: InlineAlertTone): { background: string; color: string } {
  if (tone === "success") return { background: "var(--success-muted)", color: "var(--success)" };
  if (tone === "info") return { background: "var(--info-muted)", color: "var(--info)" };
  if (tone === "warning") return { background: "var(--warning-muted)", color: "var(--warning)" };
  return { background: "var(--danger-muted)", color: "var(--danger)" };
}

export function InlineAlert({ tone = "danger", children, className, style }: InlineAlertProps) {
  const vars = resolveToneVars(tone);

  return (
    <div
      className={className}
      style={{
        marginTop: "var(--space-4)",
        padding: "var(--space-3)",
        borderRadius: "var(--radius-md)",
        fontSize: "0.875rem",
        background: vars.background,
        color: vars.color,
        ...style,
      }}
    >
      {children}
    </div>
  );
}

