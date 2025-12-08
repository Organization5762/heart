import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/peripherals/connected')({
  component: RouteComponent,
})

function RouteComponent() {
  return <div>Hello "/peripherals/connected"!</div>
}
