import { PeripheralTree } from "@/actions/peripherals/peripheral_tree";
import {
  PageFrame,
  PaperCard,
  SectionHeader,
  SpecChip,
} from "@/components/usgc";
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
          description="Active input hardware grouped by capability and mode, presented as a U.S.G.C. engineering sheet."
          aside={<SpecChip tone="muted">Input Variant / Mode</SpecChip>}
        />
      </PaperCard>
      <PeripheralTree hierarchy={[["input_variant", "mode"]]} />
    </PageFrame>
  );
}
