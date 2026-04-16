import * as React from "react";

import { cn } from "@/lib/utils";

const Checkbox = React.forwardRef<HTMLInputElement, React.ComponentProps<"input">>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      type="checkbox"
      className={cn(
        "size-4 rounded border border-[var(--border-strong)] bg-[var(--bg-surface)] text-primary accent-[var(--primary)] outline-none transition-[border-color,box-shadow] disabled:cursor-not-allowed disabled:opacity-50 focus:ring-3 focus:ring-[var(--primary-muted)]",
        className,
      )}
      {...props}
    />
  ),
);

Checkbox.displayName = "Checkbox";

export { Checkbox };
