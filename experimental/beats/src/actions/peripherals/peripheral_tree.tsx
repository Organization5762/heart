import { AccelerometerView } from "@/components/ui/peripherals/accelerometer";
import { GenericSensorPeripheralView } from "@/components/ui/peripherals/generic_sensor";
import { RotarySwitchView } from "@/components/ui/peripherals/rotary_button";
import { UWBPositionView } from "@/components/ui/peripherals/uwb_positioning";
import { PaperCard, SpecChip } from "@/components/beats-shell";
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

type PeripheralHierarchyNode = {
  key: string;
  label: string;
  tagName: string;
  count: number;
  children: PeripheralHierarchyNode[];
  peripherals: PeripheralSnapshot[];
};

const DEFAULT_HIERARCHY_HEADING = "Connected Peripherals";
const UNSPECIFIED_VARIANT = "Unspecified";

function tagsByName(peripheral: PeripheralInfo) {
  return Object.fromEntries(peripheral.tags.map((t) => [t.name, t]));
}

function findTagVariant(peripheral: PeripheralInfo, tagName: string) {
  return peripheral.tags.find((tag) => tag.name === tagName)?.variant;
}

function formatHierarchyLabel(tagName: string, variant: string) {
  return `${tagName.replaceAll("_", " ")} / ${variant}`;
}

function buildHierarchyTree(
  peripheralEntries: PeripheralSnapshot[],
  hierarchy: string[],
  depth = 0,
): PeripheralHierarchyNode[] {
  if (depth >= hierarchy.length) {
    return [];
  }

  const tagName = hierarchy[depth];
  const groupedEntries = new Map<string, PeripheralSnapshot[]>();

  peripheralEntries.forEach((snapshot) => {
    const variant =
      findTagVariant(snapshot.info, tagName) ?? UNSPECIFIED_VARIANT;
    const existing = groupedEntries.get(variant);

    if (existing) {
      existing.push(snapshot);
      return;
    }

    groupedEntries.set(variant, [snapshot]);
  });

  return Array.from(groupedEntries.entries())
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([variant, snapshots]) => ({
      key: `${tagName}:${variant}`,
      label: formatHierarchyLabel(tagName, variant),
      tagName,
      count: snapshots.length,
      children: buildHierarchyTree(snapshots, hierarchy, depth + 1),
      peripherals: depth === hierarchy.length - 1 ? snapshots : [],
    }));
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
              <p className="beats-kicker">{DEFAULT_HIERARCHY_HEADING}</p>
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
            <div className="grid gap-4">
              {buildHierarchyTree(peripheralEntries, h).map((node) => (
                <HierarchyBranch
                  key={node.key}
                  hierarchy={h}
                  node={node}
                  depth={0}
                />
              ))}
            </div>
          )}
        </PaperCard>
      ))}
    </div>
  );
}

function HierarchyBranch({
  depth,
  hierarchy,
  node,
}: {
  depth: number;
  hierarchy: string[];
  node: PeripheralHierarchyNode;
}) {
  return (
    <section
      className="border-border/70 bg-background/40 space-y-4 border border-dashed p-4"
      style={{ marginLeft: `${depth * 1.25}rem` }}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <p className="text-muted-foreground font-mono text-[0.68rem] tracking-[0.18em] uppercase">
            {node.tagName.replaceAll("_", " ")}
          </p>
          <h3 className="font-tomorrow text-lg tracking-[0.08em]">
            {node.label}
          </h3>
        </div>
        <SpecChip tone="muted">{node.count} Units</SpecChip>
      </div>
      {node.children.length > 0 ? (
        <div className="grid gap-4">
          {node.children.map((child) => (
            <HierarchyBranch
              key={`${node.key}/${child.key}`}
              depth={depth + 1}
              hierarchy={hierarchy}
              node={child}
            />
          ))}
        </div>
      ) : (
        <div className="grid gap-4 xl:grid-cols-2">
          {node.peripherals.map((snapshot) => (
            <PeripheralBranch
              key={snapshot.info.id ?? `unknown-${snapshot.ts}`}
              snapshot={snapshot}
              hierarchy={hierarchy}
            />
          ))}
        </div>
      )}
    </section>
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
  const orderedTags = peripheral.tags
    .filter((t) => !hierarchy.includes(t.name))
    .sort((a, b) => a.name.localeCompare(b.name));

  return (
    <div className="border-border bg-background/70 border p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-2">
          <p className="beats-kicker">Peripheral</p>
          <h3 className="font-tomorrow text-xl tracking-[0.08em]">
            {peripheral.id ?? "Unknown Unit"}
          </h3>
        </div>
        <SpecChip tone="muted">
          {orderedTags.length > 0 ? `${orderedTags.length} Tags` : "Preview"}
        </SpecChip>
      </div>

      <div
        className={
          "mt-4 grid gap-4 " +
          (orderedTags.length > 0 ? "lg:grid-cols-[220px_1fr]" : "")
        }
      >
        {orderedTags.length > 0 ? (
          <div className="space-y-1">
            {orderedTags.map((tag, idx) => (
              <TagNode key={`${tag.name}-${idx}`} tag={tag} depth={idx} />
            ))}
          </div>
        ) : null}
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
