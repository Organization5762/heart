import { cn } from "@/utils/tailwind";
import type { ComponentProps, ReactNode } from "react";

export function PageFrame({ className, ...props }: ComponentProps<"div">) {
  return <div className={cn("usgc-page", className)} {...props} />;
}

export function PaperCard({ className, ...props }: ComponentProps<"section">) {
  return <section className={cn("usgc-card", className)} {...props} />;
}

export function TechnicalCard({
  className,
  ...props
}: ComponentProps<"section">) {
  return (
    <section className={cn("usgc-card usgc-card-dark", className)} {...props} />
  );
}

type SectionHeaderProps = {
  eyebrow: string;
  title: string;
  description?: ReactNode;
  aside?: ReactNode;
  className?: string;
  invert?: boolean;
};

export function SectionHeader({
  eyebrow,
  title,
  description,
  aside,
  className,
  invert = false,
}: SectionHeaderProps) {
  return (
    <div
      className={cn(
        "flex flex-col gap-4 md:flex-row md:items-start md:justify-between",
        className,
      )}
    >
      <div className="min-w-0 flex-1 space-y-2">
        <p className={cn("usgc-kicker", invert && "text-[#bdb3a6]")}>
          {eyebrow}
        </p>
        <h1
          className={cn(
            "font-tomorrow text-3xl tracking-[0.06em] break-words md:text-4xl",
            invert ? "text-[#f6efe6]" : "text-foreground",
          )}
        >
          {title}
        </h1>
        {description ? (
          <div
            className={cn(
              "max-w-3xl text-sm leading-7",
              invert ? "text-[#d8cfc1]" : "text-[#3b3228] dark:text-[#d8cfc1]",
            )}
          >
            {description}
          </div>
        ) : null}
      </div>
      {aside ? (
        <div className="max-w-full self-start md:max-w-[40%] md:text-right">
          {aside}
        </div>
      ) : null}
    </div>
  );
}

export function SpecChip({
  className,
  tone = "default",
  ...props
}: ComponentProps<"span"> & {
  tone?: "default" | "muted" | "dark";
}) {
  return (
    <span
      className={cn(
        "usgc-chip whitespace-normal",
        tone === "muted" && "usgc-chip-muted",
        tone === "dark" && "usgc-chip-dark",
        className,
      )}
      {...props}
    />
  );
}

export function DataRow({
  label,
  value,
  className,
  labelClassName,
  valueClassName,
}: {
  label: string;
  value: ReactNode;
  className?: string;
  labelClassName?: string;
  valueClassName?: string;
}) {
  return (
    <div className={cn("usgc-data-row", className)}>
      <span className={cn("usgc-data-label", labelClassName)}>{label}</span>
      <span className={cn("min-w-0 break-words", valueClassName)}>{value}</span>
    </div>
  );
}

export function MeterBar({
  label,
  value,
  max = 100,
  valueLabel,
  className,
}: {
  label: string;
  value: number;
  max?: number;
  valueLabel?: ReactNode;
  className?: string;
}) {
  const percent = Math.max(0, Math.min(100, (value / max) * 100));

  return (
    <div className={cn("space-y-1", className)}>
      <div className="flex items-center justify-between gap-3 font-mono text-[0.7rem] tracking-[0.18em] uppercase">
        <span className="text-muted-foreground">{label}</span>
        <span>{valueLabel ?? `${percent.toFixed(0)}%`}</span>
      </div>
      <div className="usgc-meter">
        <div className="usgc-meter-fill" style={{ width: `${percent}%` }} />
      </div>
    </div>
  );
}
