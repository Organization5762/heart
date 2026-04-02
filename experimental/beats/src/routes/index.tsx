import { getAppVersion } from "@/actions/app";
import { usePeripheralEvents } from "@/actions/ws/providers/PeripheralEventsProvider";
import { useConnectedPeripherals } from "@/actions/ws/providers/PeripheralProvider";
import { useStreamedImage } from "@/actions/ws/providers/ImageProvider";
import { useWS } from "@/actions/ws/websocket";
import {
  DataRow,
  MeterBar,
  PageFrame,
  PaperCard,
  SectionHeader,
  SpecChip,
  TechnicalCard,
} from "@/components/beats-shell";
import {
  DISABLED_WEBSOCKET_LABEL,
  getConfiguredBeatsWebSocketUrl,
} from "@/config/websocket";
import { Link, createFileRoute } from "@tanstack/react-router";
import { Binary, Mouse, RadioTower, ScanLine, Tv } from "lucide-react";
import { useEffect, useState, useTransition } from "react";

const RECENT_DEVICE_LIMIT = 4;
const RECENT_ACTIVITY_WINDOW_MS = 60_000;
const RECENT_ACTIVITY_TICK_MS = 5_000;
const configuredWebsocketUrl = getConfiguredBeatsWebSocketUrl();

const routeCards = [
  {
    title: "Current Stream",
    description:
      "The live image chamber with machine report details, cadence readout, and transmission health.",
    href: "/stream",
    icon: Tv,
  },
  {
    title: "Peripherals",
    description:
      "Connected devices, event logs, and the latest payload snapshots in one technical catalog.",
    href: "/peripherals/connected",
    icon: Mouse,
  },
];

function getReadyStateLabel(readyState: number) {
  switch (readyState) {
    case WebSocket.CONNECTING:
      return "Dialing";
    case WebSocket.OPEN:
      return "Online";
    case WebSocket.CLOSING:
      return "Closing";
    default:
      return "Offline";
  }
}

type HomePeripheralSnapshot = ReturnType<
  typeof useConnectedPeripherals
>[string];
type HomePeripheralEvent = ReturnType<typeof usePeripheralEvents>[number];

export type RecentPeripheralActivity = {
  id: string;
  lastSeenTs: number;
  eventCount: number;
};

export function selectStableRecentPeripheralActivity(
  previousVisibleIds: string[],
  activeDevices: RecentPeripheralActivity[],
  limit = RECENT_DEVICE_LIMIT,
): RecentPeripheralActivity[] {
  const activeById = new Map(
    activeDevices.map((activity) => [activity.id, activity] as const),
  );
  const stableVisibleDevices: RecentPeripheralActivity[] = [];
  const seenIds = new Set<string>();

  for (const id of previousVisibleIds) {
    const activity = activeById.get(id);
    if (!activity) {
      continue;
    }

    stableVisibleDevices.push(activity);
    seenIds.add(id);
  }

  for (const activity of activeDevices) {
    if (seenIds.has(activity.id)) {
      continue;
    }

    stableVisibleDevices.push(activity);
    seenIds.add(activity.id);
  }

  return stableVisibleDevices.slice(0, limit);
}

export function summarizeRecentPeripheralActivity(
  peripheralEntries: HomePeripheralSnapshot[],
  events: HomePeripheralEvent[],
  now: number,
): RecentPeripheralActivity[] {
  const activityById = new Map<string, RecentPeripheralActivity>();

  for (const event of events) {
    const peripheralId = event.msg.payload.peripheralInfo.id;
    if (!peripheralId) {
      continue;
    }

    const existing = activityById.get(peripheralId);
    if (existing) {
      existing.eventCount += 1;
      existing.lastSeenTs = Math.max(existing.lastSeenTs, event.ts);
      continue;
    }

    activityById.set(peripheralId, {
      id: peripheralId,
      lastSeenTs: event.ts,
      eventCount: 1,
    });
  }

  for (const peripheral of peripheralEntries) {
    const peripheralId = peripheral.info.id;
    if (!peripheralId) {
      continue;
    }

    const existing = activityById.get(peripheralId);
    if (existing) {
      existing.lastSeenTs = Math.max(existing.lastSeenTs, peripheral.ts);
      continue;
    }

    activityById.set(peripheralId, {
      id: peripheralId,
      lastSeenTs: peripheral.ts,
      eventCount: 0,
    });
  }

  return [...activityById.values()]
    .filter(
      (activity) => now - activity.lastSeenTs <= RECENT_ACTIVITY_WINDOW_MS,
    )
    .sort((left, right) => {
      if (right.lastSeenTs !== left.lastSeenTs) {
        return right.lastSeenTs - left.lastSeenTs;
      }

      if (right.eventCount !== left.eventCount) {
        return right.eventCount - left.eventCount;
      }

      return left.id.localeCompare(right.id);
    });
}

export function formatPeripheralRecency(
  lastSeenTs: number,
  now: number,
): string {
  const deltaSeconds = Math.max(0, Math.floor((now - lastSeenTs) / 1_000));

  if (deltaSeconds < 5) {
    return "Just now";
  }

  if (deltaSeconds < 60) {
    return `${deltaSeconds}s ago`;
  }

  const deltaMinutes = Math.floor(deltaSeconds / 60);
  return `${deltaMinutes}m ago`;
}

function HomePage() {
  const ws = useWS();
  const { fps, isActive } = useStreamedImage();
  const peripherals = useConnectedPeripherals();
  const events = usePeripheralEvents();
  const [appVersion, setAppVersion] = useState("0.0.0");
  const [now, setNow] = useState(() => Date.now());
  const [, startGetAppVersion] = useTransition();

  useEffect(
    () => startGetAppVersion(() => getAppVersion().then(setAppVersion)),
    [],
  );

  useEffect(() => {
    const intervalId = window.setInterval(
      () => setNow(Date.now()),
      RECENT_ACTIVITY_TICK_MS,
    );
    return () => window.clearInterval(intervalId);
  }, []);

  const peripheralEntries = Object.values(peripherals).sort(
    (left, right) => right.ts - left.ts,
  );
  const readyStateLabel = getReadyStateLabel(ws.readyState);
  const activePeripheralActivity = summarizeRecentPeripheralActivity(
    peripheralEntries,
    events,
    now,
  );

  return (
    <PageFrame>
      <section className="grid gap-6 xl:grid-cols-[1.18fr_0.82fr]">
        <PaperCard className="flex flex-col justify-between gap-8">
          <SectionHeader
            eyebrow="Beats / Telemetry Division"
            title="Beats Telemetry Catalog"
            description={
              <>
                A paper-specimen shell for device-facing signal work: live
                streaming, machine reports, and peripheral surveillance arranged
                as one technical publication.
              </>
            }
          />
          <div className="flex flex-wrap gap-2">
            <SpecChip>Type Specimen</SpecChip>
            <SpecChip tone="muted">TX-24</SpecChip>
            <SpecChip tone="muted">TR-100</SpecChip>
            <SpecChip tone="muted">
              {isActive ? "Live Feed Active" : "Awaiting Feed"}
            </SpecChip>
          </div>
          <div className="grid gap-4 md:grid-cols-3">
            <div className="border-border bg-background/75 border p-4">
              <p className="beats-kicker">Signal</p>
              <p className="font-tomorrow mt-3 text-2xl tracking-[0.14em]">
                {readyStateLabel}
              </p>
              <p className="text-muted-foreground mt-2 font-mono text-[0.72rem] tracking-[0.18em] uppercase">
                Transport readiness
              </p>
            </div>
            <div className="border-border bg-background/75 border p-4">
              <p className="beats-kicker">Cadence</p>
              <p className="font-tomorrow mt-3 text-2xl tracking-[0.14em]">
                {isActive ? fps : 0} FPS
              </p>
              <p className="text-muted-foreground mt-2 font-mono text-[0.72rem] tracking-[0.18em] uppercase">
                Recent frame rate
              </p>
            </div>
            <div className="border-border bg-background/75 border p-4">
              <p className="beats-kicker">Devices</p>
              <p className="font-tomorrow mt-3 text-2xl tracking-[0.14em]">
                {peripheralEntries.length}
              </p>
              <p className="text-muted-foreground mt-2 font-mono text-[0.72rem] tracking-[0.18em] uppercase">
                Connected peripherals
              </p>
            </div>
          </div>
        </PaperCard>

        <TechnicalCard className="flex flex-col gap-6">
          <SectionHeader
            eyebrow="TR-100 Machine Report"
            title="Operational Summary"
            invert
          />
          <div className="space-y-1 font-mono text-sm">
            <DataRow label="Program" value="Beats Telemetry Terminal" />
            <DataRow label="Version" value={appVersion} />
            <DataRow
              label="Signal"
              value={
                ws.socket?.url ??
                configuredWebsocketUrl ??
                DISABLED_WEBSOCKET_LABEL
              }
            />
            <DataRow label="Socket" value={readyStateLabel} />
            <DataRow label="Peripherals" value={peripheralEntries.length} />
            <DataRow label="Events" value={events.length} />
          </div>
          <div className="space-y-3">
            <div className="flex items-center justify-between gap-3 font-mono text-[0.7rem] tracking-[0.18em] uppercase">
              <span className="text-[#bdb3a6]">Recently Active Devices</span>
              <span>{activePeripheralActivity.length} Tracked</span>
            </div>
            {activePeripheralActivity.length > 0 ? (
              <div className="space-y-2">
                {activePeripheralActivity.map((device) => (
                  <div
                    key={device.id}
                    className="border border-[#4d4238] bg-black/10 px-3 py-2"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <span className="font-mono text-sm text-[#f6efe6]">
                        {device.id}
                      </span>
                      <span className="font-mono text-[0.7rem] tracking-[0.16em] text-[#bdb3a6] uppercase">
                        {formatPeripheralRecency(device.lastSeenTs, now)}
                      </span>
                    </div>
                    <p className="mt-1 font-mono text-[0.72rem] tracking-[0.12em] text-[#bdb3a6] uppercase">
                      {device.eventCount > 0
                        ? `${device.eventCount} updates in the last minute`
                        : "Connected, no new payload burst in the last minute"}
                    </p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-[#d8cfc1]">
                No recently active devices in the last minute.
              </p>
            )}
          </div>
          <div className="grid gap-4">
            <MeterBar
              label="Frame Cadence"
              value={Math.min(isActive ? fps : 0, 60)}
              max={60}
              valueLabel={`${isActive ? fps : 0} FPS`}
            />
            <MeterBar
              label="Peripheral Coverage"
              value={Math.min(peripheralEntries.length, 8)}
              max={8}
              valueLabel={`${peripheralEntries.length} Units`}
            />
          </div>
        </TechnicalCard>
      </section>

      <section>
        <PaperCard className="flex flex-col gap-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="space-y-2">
              <p className="beats-kicker">Typeface / TX-24</p>
              <h2 className="font-tomorrow text-3xl tracking-[0.1em]">
                Beats Monitor
              </h2>
            </div>
            <div className="flex flex-wrap gap-2">
              <SpecChip>Telemetry</SpecChip>
              <SpecChip tone="muted">Machine Report</SpecChip>
            </div>
          </div>
          <p className="beats-copy max-w-3xl">
            Space grade, device-facing, and unapologetically procedural. Beats
            Monitor is a control-room type system for live image transport,
            sensor traffic, and synchronized playback. It treats interface
            chrome like documentation and every page like a technical sheet.
          </p>
          <div className="grid gap-4 md:grid-cols-3">
            <div className="border-border bg-background/75 border p-4">
              <RadioTower className="text-foreground size-5" />
              <p className="font-tomorrow mt-4 text-lg tracking-[0.12em]">
                Stream
              </p>
              <p className="text-muted-foreground mt-2 text-sm">
                Live imaging, failover, and machine-state framing.
              </p>
            </div>
            <div className="border-border bg-background/75 border p-4">
              <Binary className="text-foreground size-5" />
              <p className="font-tomorrow mt-4 text-lg tracking-[0.12em]">
                Logs
              </p>
              <p className="text-muted-foreground mt-2 text-sm">
                Event payloads set in mono and exposed without decoration.
              </p>
            </div>
            <div className="border-border bg-background/75 border p-4">
              <ScanLine className="text-foreground size-5" />
              <p className="font-tomorrow mt-4 text-lg tracking-[0.12em]">
                Sensors
              </p>
              <p className="text-muted-foreground mt-2 text-sm">
                Visualized device data organized as specimen cards.
              </p>
            </div>
          </div>
        </PaperCard>
      </section>

      <section className="grid gap-4 lg:grid-cols-3">
        {routeCards.map((card) => (
          <Link key={card.href} to={card.href} className="beats-link-card">
            <PaperCard className="h-full">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="beats-kicker">Open</p>
                  <h2 className="font-tomorrow mt-3 text-2xl tracking-[0.08em]">
                    {card.title}
                  </h2>
                </div>
                <card.icon className="text-foreground mt-1 size-5" />
              </div>
              <p className="text-muted-foreground mt-4 text-sm leading-7">
                {card.description}
              </p>
            </PaperCard>
          </Link>
        ))}
      </section>
    </PageFrame>
  );
}

export const Route = createFileRoute("/")({
  component: HomePage,
});
