import { PeripheralTree } from "@/actions/peripherals/peripheral_tree";
import { PeripheralSensorDeck } from "@/components/peripheral-sensor-deck";
import {
  PageFrame,
  PaperCard,
  SectionHeader,
  SpecChip,
} from "@/components/beats-shell";
import { createFileRoute } from "@tanstack/react-router";
import { z } from "zod";

export const Route = createFileRoute("/peripherals/connected")({
  validateSearch: z.object({
    sensor: z.string().optional(),
  }),
  component: RouteComponent,
});

function RouteComponent() {
  const search = Route.useSearch();

  return (
    <PageFrame>
      <PaperCard>
        <SectionHeader
          eyebrow="Peripherals / Connected"
          title="Device Catalog"
          description="Active input hardware grouped by capability and mode, presented as a Beats engineering sheet."
          aside={<SpecChip tone="muted">Input Variant / Mode</SpecChip>}
        />
      </PaperCard>
      <PeripheralSensorDeck preferredSensorKey={search.sensor} />
      <PeripheralTree hierarchy={[["input_variant", "mode"]]} />
    </PageFrame>
  );
}
