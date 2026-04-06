import type { ReactNode } from "react";

type EmptyStateProps = {
  size?: "small" | "normal";
  children: ReactNode;
  className?: string;
};

export function EmptyState({ size = "normal", children, className }: EmptyStateProps) {
  return <div className={`empty-state empty-state--${size}${className ? ` ${className}` : ""}`}>{children}</div>;
}

