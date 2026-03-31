import { PeripheralSnapshots } from "@/actions/peripherals/peripheral_snapshots";
import {
  PageFrame,
  PaperCard,
  SectionHeader,
  SpecChip,
} from "@/components/beats-shell";
import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/peripherals/snapshots")({
  component: RouteComponent,
});

function RouteComponent() {
  return (
    <PageFrame>
      <PaperCard>
        <SectionHeader
          eyebrow="Peripherals / Snapshots"
          title="Latest Data Sheets"
          description="Recent payload state for every connected peripheral, preserved as a snapshot table."
          aside={<SpecChip tone="muted">Most Recent First</SpecChip>}
        />
      </PaperCard>
      <PeripheralSnapshots />
    </PageFrame>
  );
}
