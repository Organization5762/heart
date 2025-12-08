import { PeripheralTree } from '@/actions/peripherals/peripheral_tree';
import { createFileRoute } from '@tanstack/react-router';

export const Route = createFileRoute('/peripherals/connected')({
  component: RouteComponent,
})

function RouteComponent() {
  return <PeripheralTree hierarchy={[["input_variant", "mode"]]} />
}
