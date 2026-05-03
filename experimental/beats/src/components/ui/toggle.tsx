import type { ComponentProps } from "react";
import { Root as ToggleRoot } from "@radix-ui/react-toggle";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/utils/tailwind";

const toggleVariants = cva(
  "inline-flex items-center justify-center gap-2 rounded-[3px] border border-border bg-background text-[0.72rem] font-tomorrow font-medium uppercase tracking-[0.16em] hover:bg-secondary hover:text-secondary-foreground disabled:pointer-events-none disabled:opacity-50 data-[state=on]:bg-primary data-[state=on]:text-primary-foreground [&_svg]:pointer-events-none [&_svg:not([class*='size-'])]:size-4 [&_svg]:shrink-0 focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px] outline-none transition-[color,box-shadow] aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40 aria-invalid:border-destructive whitespace-nowrap",
  {
    variants: {
      variant: {
        default: "shadow-[2px_2px_0_rgba(0,0,0,0.06)]",
        outline:
          "border-input bg-transparent shadow-[2px_2px_0_rgba(0,0,0,0.06)] hover:bg-secondary hover:text-secondary-foreground",
      },
      size: {
        default: "h-9 px-2 min-w-9",
        sm: "h-8 px-1.5 min-w-8",
        lg: "h-10 px-2.5 min-w-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
);

function Toggle({
  className,
  variant,
  size,
  ...props
}: ComponentProps<typeof ToggleRoot> & VariantProps<typeof toggleVariants>) {
  return (
    <ToggleRoot
      data-slot="toggle"
      className={cn(toggleVariants({ variant, size, className }))}
      {...props}
    />
  );
}

export { Toggle, toggleVariants };
