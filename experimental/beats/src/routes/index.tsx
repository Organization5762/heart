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
} from "@/components/usgc";
import { Link, createFileRoute } from "@tanstack/react-router";
import { Binary, Mouse, Orbit, RadioTower, ScanLine, Tv } from "lucide-react";
import { useEffect, useState, useTransition } from "react";

const routeCards = [
  {
    title: "Mission Control",
    description:
      "A specimen-grade rehearsal console for phase timing, subsystem health, and playback control.",
    href: "/mission-control",
    icon: Orbit,
  },
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

function HomePage() {
  const ws = useWS();
  const { fps, isActive } = useStreamedImage();
  const peripherals = useConnectedPeripherals();
  const events = usePeripheralEvents();
  const [appVersion, setAppVersion] = useState("0.0.0");
  const [, startGetAppVersion] = useTransition();

  useEffect(
    () => startGetAppVersion(() => getAppVersion().then(setAppVersion)),
    [],
  );

  const peripheralEntries = Object.values(peripherals).sort(
    (left, right) => right.ts - left.ts,
  );
  const latestPeripheral = peripheralEntries[0];
  const readyStateLabel = getReadyStateLabel(ws.readyState);

  return (
    <PageFrame>
      <section className="grid gap-6 xl:grid-cols-[1.18fr_0.82fr]">
        <PaperCard className="flex flex-col justify-between gap-8">
          <SectionHeader
            eyebrow="U.S. Graphics Company / Beats Division"
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
              <p className="usgc-kicker">Signal</p>
              <p className="font-tomorrow mt-3 text-2xl tracking-[0.14em]">
                {readyStateLabel}
              </p>
              <p className="text-muted-foreground mt-2 font-mono text-[0.72rem] tracking-[0.18em] uppercase">
                Transport readiness
              </p>
            </div>
            <div className="border-border bg-background/75 border p-4">
              <p className="usgc-kicker">Cadence</p>
              <p className="font-tomorrow mt-3 text-2xl tracking-[0.14em]">
                {isActive ? fps : 0} FPS
              </p>
              <p className="text-muted-foreground mt-2 font-mono text-[0.72rem] tracking-[0.18em] uppercase">
                Recent frame rate
              </p>
            </div>
            <div className="border-border bg-background/75 border p-4">
              <p className="usgc-kicker">Devices</p>
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
            aside={
              <SpecChip tone="dark">United States Graphics Company</SpecChip>
            }
          />
          <div className="space-y-1 font-mono text-sm">
            <DataRow label="Program" value="Beats Telemetry Terminal" />
            <DataRow label="Version" value={appVersion} />
            <DataRow
              label="Signal"
              value={ws.socket?.url ?? "ws://localhost:8765"}
            />
            <DataRow label="Socket" value={readyStateLabel} />
            <DataRow label="Peripherals" value={peripheralEntries.length} />
            <DataRow label="Events" value={events.length} />
            <DataRow
              label="Last Device"
              value={latestPeripheral?.info.id ?? "No peripheral registered"}
            />
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
              <p className="usgc-kicker">Typeface / TX-24</p>
              <h2 className="font-tomorrow text-3xl tracking-[0.1em]">
                Beats Monitor
              </h2>
            </div>
            <div className="flex flex-wrap gap-2">
              <SpecChip>Telemetry</SpecChip>
              <SpecChip tone="muted">Machine Report</SpecChip>
            </div>
          </div>
          <p className="usgc-copy max-w-3xl">
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
          <Link key={card.href} to={card.href} className="usgc-link-card">
            <PaperCard className="h-full">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="usgc-kicker">Open</p>
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
