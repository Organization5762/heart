import { PeripheralTree } from "@/actions/peripherals/peripheral_tree";
import { PeripheralSensorDeck } from "@/components/peripheral-sensor-deck";
import {
  PageFrame,
  PaperCard,
  SectionHeader,
  SpecChip,
} from "@/components/beats-shell";
import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/peripherals/connected")({
  component: RouteComponent,
});

function RouteComponent() {
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
      <PeripheralSensorDeck />
      <PeripheralTree hierarchy={[["input_variant", "mode"]]} />
    </PageFrame>
  );
}
