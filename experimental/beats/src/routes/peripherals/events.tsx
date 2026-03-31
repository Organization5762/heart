import { EventList } from "@/actions/peripherals/event_list";
import {
  PageFrame,
  PaperCard,
  SectionHeader,
  SpecChip,
} from "@/components/beats-shell";
import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/peripherals/events")({
  component: RouteComponent,
});

function RouteComponent() {
  return (
    <PageFrame>
      <PaperCard>
        <SectionHeader
          eyebrow="Peripherals / Events"
          title="Signal Transcript"
          description="A rolling event record for incoming device traffic, structured like an engineering bulletin."
          aside={<SpecChip tone="muted">Latest 100 Entries</SpecChip>}
        />
      </PaperCard>
      <EventList />
    </PageFrame>
  );
}
