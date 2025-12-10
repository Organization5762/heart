import { AccelerometerView } from "@/components/ui/peripherals/accelerometer";
import { RotarySwitchView } from "@/components/ui/peripherals/rotary_button";
import { UWBPositionView } from "@/components/ui/peripherals/uwb_positioning";
import { Tooltip, TooltipContent, TooltipTrigger } from "../../components/ui/tooltip";
import { PeripheralInfo, PeripheralTag, useConnectedPeripherals } from "../ws/providers/PeripheralProvider";

function tagsByName(peripheral: PeripheralInfo) {
  return Object.fromEntries(
    peripheral.tags.map((t) => [t.name, t])
  );
};

const SpecialRenderer = ({ peripheral }: { peripheral: PeripheralInfo }) => {
  const c = tagsByName(peripheral);
  switch (c["input_variant"].variant) {
    case "uwb_positioning":
      return <UWBPositionView peripheral={peripheral} />
    case "accelerometer":
      return <AccelerometerView peripheral={peripheral} />
    case "button":
      return <RotarySwitchView peripheral={peripheral} />
    default:
      return <span>{peripheral.id}</span>
  }
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
    <div className="p-3 text-xs font-mono max-h-[95vh] overflow-y-auto scrollbar-thin scrollbar-thumb-gray-300 scrollbar-track-gray-100">
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
  // Tags in the desired order
  const orderedTags = [
    ...hierarchy.map((name) => tagsByName(peripheral)[name]).filter(Boolean),
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
        depth={orderedTags.length}
        renderAsComponent={<SpecialRenderer peripheral={peripheral} />}
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
  depth,
  renderAsComponent,
}: {
  depth: number;
  renderAsComponent?: React.ReactNode;
}) {
  return (
    <div
      className="mt-2 font-semibold"
      style={{ marginLeft: depth * 16 }}
    >
      {renderAsComponent}
    </div>
  );
}
