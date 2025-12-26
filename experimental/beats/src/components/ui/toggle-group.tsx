"use client";

import { createContext, useContext } from "react";
import type { ComponentProps } from "react";
import {
  Item as ToggleGroupItemPrimitive,
  Root as ToggleGroupRoot,
} from "@radix-ui/react-toggle-group";
import { type VariantProps } from "class-variance-authority";

import { cn } from "@/utils/tailwind";
import { toggleVariants } from "@/components/ui/toggle";

const ToggleGroupContext = createContext<
  VariantProps<typeof toggleVariants>
>({
  size: "default",
  variant: "default",
});

function ToggleGroup({
  className,
  variant,
  size,
  children,
  ...props
}: ComponentProps<typeof ToggleGroupRoot> &
  VariantProps<typeof toggleVariants>) {
  return (
    <ToggleGroupRoot
      data-slot="toggle-group"
      data-variant={variant}
      data-size={size}
      className={cn(
        "group/toggle-group flex w-fit items-center rounded-md data-[variant=outline]:shadow-xs",
        className,
      )}
      {...props}
    >
      <ToggleGroupContext.Provider value={{ variant, size }}>
        {children}
      </ToggleGroupContext.Provider>
    </ToggleGroupRoot>
  );
}

function ToggleGroupItem({
  className,
  children,
  variant,
  size,
  ...props
}: ComponentProps<typeof ToggleGroupItemPrimitive> &
  VariantProps<typeof toggleVariants>) {
  const context = useContext(ToggleGroupContext);

  return (
    <ToggleGroupItemPrimitive
      data-slot="toggle-group-item"
      data-variant={context.variant || variant}
      data-size={context.size || size}
      className={cn(
        toggleVariants({
          variant: context.variant || variant,
          size: context.size || size,
        }),
        "min-w-0 flex-1 shrink-0 rounded-none shadow-none first:rounded-l-md last:rounded-r-md focus:z-10 focus-visible:z-10 data-[variant=outline]:border-l-0 data-[variant=outline]:first:border-l",
        className,
      )}
      {...props}
    >
      {children}
    </ToggleGroupItemPrimitive>
  );
}

export { ToggleGroup, ToggleGroupItem };
