import { createFileRoute } from '@tanstack/react-router'

import {
  Stream
} from "@/components/stream"
function RouteComponent() {
  return <Stream/>
}

export const Route = createFileRoute('/stream/')({
  component: RouteComponent,
})