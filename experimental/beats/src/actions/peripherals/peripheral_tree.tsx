import { Tooltip, TooltipContent, TooltipTrigger } from "../../components/ui/tooltip";
import { useConnectedPeripherals } from "../ws/providers/PeripheralProvider";

type PeripheralTag = {
  name: string;
  variant: string;
  metadata?: Record<string, string>;
};

type PeripheralInfo = {
  id?: string | null;
  tags: PeripheralTag[];
};

export function PeripheralTree({
  hierarchy = [],
}: {
  hierarchy: string[] | string[][];
}) {
  const peripherals = useConnectedPeripherals();

  const hierarchies: string[][] = Array.isArray(hierarchy[0])
    ? (hierarchy as string[][])
    : [hierarchy as string[]];

  return (
    <div className="p-3 text-xs font-mono select-none">
      {hierarchies.map((h, idx) => (
        <div key={idx} className={hierarchies.length > 1 ? "mb-6" : ""}>
          <span className="text-sm font-bold mb-2">
            {h.join(" / ")}
          </span>
          {Object.values(peripherals).map((p) => (
            <PeripheralBranch
              key={p.info.id ?? `unknown-${p.ts}`}
              peripheral={p.info}
              hierarchy={h}
            />
          ))}
        </div>
      ))}
    </div>
  );
}

function PeripheralBranch({
  peripheral,
  hierarchy,
}: {
  peripheral: PeripheralInfo;
  hierarchy: string[];
}) {
  const tagsByName = Object.fromEntries(
    peripheral.tags.map((t) => [t.name, t])
  );

  // Tags in the desired order
  const orderedTags = [
    ...hierarchy.map((name) => tagsByName[name]).filter(Boolean),
    ...peripheral.tags
      .filter((t) => !hierarchy.includes(t.name))
      .sort((a, b) => a.name.localeCompare(b.name)),
  ];

  return (
    <div className="mb-4">
      {orderedTags.map((tag, idx) => (
        <TagNode key={idx} tag={tag} depth={idx} />
      ))}

      {/* Peripheral name at the final leaf */}
      <LeafPeripheralName
        name={peripheral.id ?? "unknown"}
        depth={orderedTags.length}
      />
    </div>
  );
}

function TagNode({ tag, depth }: { tag: PeripheralTag; depth: number }) {
    const base = depth * 16;

    return (
        <div className="mb-2">
        <Tooltip delayDuration={500}>
        <TooltipTrigger className="cursor-default">
          <div
            className="text-muted-foreground"
            style={{ marginLeft: base }}
          >
            {tag.variant}/
          </div>
          </TooltipTrigger>
          <TooltipContent>
                <p>{tag.name}</p>
          </TooltipContent>
        </Tooltip>
        </div>
      );
}

function LeafPeripheralName({
  name,
  depth,
}: {
  name: string;
  depth: number;
}) {
  return (
    <div
      className="mt-2 font-semibold"
      style={{ marginLeft: depth * 16 }}
    >
      {name}
    </div>
  );
}
