import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-[var(--radius-md)] border text-sm font-medium transition-[background-color,border-color,color,box-shadow] duration-150 outline-none disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default: "border-transparent bg-primary text-primary-foreground hover:brightness-110 hover:shadow-[var(--shadow-glow-primary)]",
        secondary:
          "border-[color:var(--border-default)] bg-secondary text-[var(--text-secondary)] hover:bg-[var(--bg-surface-overlay)] hover:text-foreground",
        outline: "border-[color:var(--border-default)] bg-transparent text-foreground hover:bg-[var(--bg-surface-elevated)]",
        ghost:
          "border-[color:var(--border-default)] bg-transparent text-[var(--text-secondary)] hover:bg-[var(--bg-surface-elevated)] hover:border-[color:var(--border-strong)] hover:text-foreground",
        destructive:
          "border-destructive bg-[var(--danger-muted)] text-destructive hover:bg-destructive hover:text-destructive-foreground",
      },
      size: {
        default: "px-4 py-2",
        sm: "px-3 py-1 text-[0.8125rem]",
        lg: "px-5 py-2.5 text-sm",
        icon: "size-9 p-0",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
);

type ButtonProps = React.ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean;
  };

function Button({ className, variant, size, asChild = false, ...props }: ButtonProps) {
  const Comp = asChild ? Slot : "button";

  return <Comp className={cn(buttonVariants({ variant, size }), className)} {...props} />;
}

export { Button, buttonVariants };
