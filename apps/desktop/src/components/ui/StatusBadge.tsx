import type { CSSProperties, ReactNode } from "react";
import { Badge } from "./badge";

type StatusBadgeProps = {
  children: ReactNode;
  tone?: string;
  className?: string;
  style?: CSSProperties;
  title?: string;
};

export function StatusBadge({ children, tone, className, style, title }: StatusBadgeProps) {
  const classes = [
    "status-badge",
    tone ? `status-badge--${tone}` : null,
    className ?? null,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <Badge variant="outline" className={classes} style={style} title={title}>
      {children}
    </Badge>
  );
}
