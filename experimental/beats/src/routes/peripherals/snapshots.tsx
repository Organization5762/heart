import { PeripheralSnapshots } from "@/actions/peripherals/peripheral_snapshots";
import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/peripherals/snapshots")({
  component: RouteComponent,
});

function RouteComponent() {
  return <PeripheralSnapshots />;
}
