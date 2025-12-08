import { EventList } from '@/actions/peripherals/event_list'
import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/peripherals/events')({
  component: RouteComponent,
})

function RouteComponent() {
  return <EventList/>
}
