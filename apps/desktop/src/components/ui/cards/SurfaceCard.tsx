import type { CSSProperties, ReactNode } from "react";

type SurfaceCardProps = {
  children: ReactNode;
  style?: CSSProperties;
};

export function SurfaceCard({ children, style }: SurfaceCardProps) {
  return (
    <div
      style={{
        padding: "var(--space-3)",
        background: "var(--bg-surface-elevated)",
        border: "1px solid var(--border-default)",
        borderRadius: "var(--radius-md)",
        ...style,
      }}
    >
      {children}
    </div>
  );
}
