import { AccelerometerView } from "@/components/ui/peripherals/accelerometer";
import { GenericSensorPeripheralView } from "@/components/ui/peripherals/generic_sensor";
import { RotarySwitchView } from "@/components/ui/peripherals/rotary_button";
import { UWBPositionView } from "@/components/ui/peripherals/uwb_positioning";
import { PaperCard, SpecChip } from "@/components/usgc";
import type { ReactNode } from "react";
import {
  PeripheralInfo,
  PeripheralTag,
  useConnectedPeripherals,
} from "../ws/providers/PeripheralProvider";

type PeripheralSnapshot = {
  ts: number;
  info: PeripheralInfo;
  last_data: unknown;
};

function tagsByName(peripheral: PeripheralInfo) {
  return Object.fromEntries(peripheral.tags.map((t) => [t.name, t]));
}

const SpecialRenderer = ({ snapshot }: { snapshot: PeripheralSnapshot }) => {
  const { info: peripheral, last_data: lastData } = snapshot;
  const c = tagsByName(peripheral);
  switch (c.input_variant?.variant) {
    case "uwb_positioning":
      return <UWBPositionView peripheral={peripheral} />;
    case "accelerometer":
      return <AccelerometerView peripheral={peripheral} />;
    case "button":
      return <RotarySwitchView peripheral={peripheral} />;
    default:
      return (
        <GenericSensorPeripheralView
          lastData={lastData}
          peripheral={peripheral}
        />
      );
  }
};

export function PeripheralTree({
  hierarchy = [],
}: {
  hierarchy: string[] | string[][];
}) {
  const peripherals = useConnectedPeripherals();
  const peripheralEntries = Object.values(peripherals).sort(
    (left, right) => right.ts - left.ts,
  );

  const hierarchies: string[][] = Array.isArray(hierarchy[0])
    ? (hierarchy as string[][])
    : [hierarchy as string[]];

  return (
    <div className="grid gap-6">
      {hierarchies.map((h, idx) => (
        <PaperCard key={idx} className="flex flex-col gap-5">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="space-y-2">
              <p className="usgc-kicker">Connected Peripherals</p>
              <h2 className="font-tomorrow text-2xl tracking-[0.1em]">
                {h.join(" / ")}
              </h2>
            </div>
            <SpecChip tone="muted">{peripheralEntries.length} Units</SpecChip>
          </div>
          {peripheralEntries.length === 0 ? (
            <p className="text-muted-foreground font-mono text-sm tracking-[0.16em] uppercase">
              Awaiting peripheral registration.
            </p>
          ) : (
            <div className="grid gap-4 xl:grid-cols-2">
              {peripheralEntries.map((p) => (
                <PeripheralBranch
                  key={p.info.id ?? `unknown-${p.ts}`}
                  snapshot={p}
                  hierarchy={h}
                />
              ))}
            </div>
          )}
        </PaperCard>
      ))}
    </div>
  );
}

function PeripheralBranch({
  snapshot,
  hierarchy,
}: {
  snapshot: PeripheralSnapshot;
  hierarchy: string[];
}) {
  const peripheral = snapshot.info;
  // Tags in the desired order
  const orderedTags = [
    ...hierarchy.map((name) => tagsByName(peripheral)[name]).filter(Boolean),
    ...peripheral.tags
      .filter((t) => !hierarchy.includes(t.name))
      .sort((a, b) => a.name.localeCompare(b.name)),
  ];

  return (
    <div className="border-border bg-background/70 border p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-2">
          <p className="usgc-kicker">Peripheral</p>
          <h3 className="font-tomorrow text-xl tracking-[0.08em]">
            {peripheral.id ?? "Unknown Unit"}
          </h3>
        </div>
        <SpecChip tone="muted">{orderedTags.length} Tags</SpecChip>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-[220px_1fr]">
        <div className="space-y-1">
          {orderedTags.map((tag, idx) => (
            <TagNode key={`${tag.name}-${idx}`} tag={tag} depth={idx} />
          ))}
        </div>
        <div className="min-w-0">
          <LeafPeripheralName
            renderAsComponent={<SpecialRenderer snapshot={snapshot} />}
          />
        </div>
      </div>
    </div>
  );
}

function TagNode({ tag, depth }: { tag: PeripheralTag; depth: number }) {
  return (
    <div className="border-border/60 grid grid-cols-[2.5rem_1fr] gap-3 border-t border-dashed py-2 first:border-t-0 first:pt-0">
      <span className="text-muted-foreground font-mono text-[0.68rem] tracking-[0.18em] uppercase">
        {String(depth + 1).padStart(2, "0")}
      </span>
      <div className="min-w-0">
        <p className="text-muted-foreground font-mono text-[0.68rem] tracking-[0.18em] uppercase">
          {tag.name}
        </p>
        <p className="text-foreground truncate text-sm">{tag.variant}</p>
      </div>
    </div>
  );
}

function LeafPeripheralName({
  renderAsComponent,
}: {
  renderAsComponent?: ReactNode;
}) {
  return <div className="min-w-0">{renderAsComponent}</div>;
}
