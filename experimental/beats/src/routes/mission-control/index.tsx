import { Button } from "@/components/ui/button";
import {
  DataRow,
  MeterBar,
  PageFrame,
  PaperCard,
  SectionHeader,
  SpecChip,
  TechnicalCard,
} from "@/components/usgc";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { createFileRoute } from "@tanstack/react-router";
import {
  CheckCircle2,
  Pause,
  Play,
  RotateCcw,
  TriangleAlert,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

type MissionPhase = {
  name: string;
  durationSeconds: number;
  objective: string;
  callout: string;
};

type SubsystemStatus = {
  name: string;
  status: "GO" | "NO GO" | "STANDBY";
  detail: string;
};

type MissionEvent = {
  timeSeconds: number;
  role: string;
  label: string;
  detail: string;
};

const missionPhases: MissionPhase[] = [
  {
    name: "Systems Warmup",
    durationSeconds: 420,
    objective: "Bring core systems online and establish baseline telemetry.",
    callout: "Control room lighting sequence green; systems online.",
  },
  {
    name: "Final Sync",
    durationSeconds: 600,
    objective: "Lock in synchronization passes and verify data loops.",
    callout: "All consoles aligned to mission tempo.",
  },
  {
    name: "Ignition Run",
    durationSeconds: 780,
    objective: "Simulated ignition and ascent sequence with load checks.",
    callout: "Primary loop stable; ascent profile nominal.",
  },
  {
    name: "Trajectory Burn",
    durationSeconds: 540,
    objective: "Commit a long-burn segment and align guidance updates.",
    callout: "Trajectory holding steady, guidance aligned.",
  },
  {
    name: "Orbit Hold",
    durationSeconds: 720,
    objective: "Stabilize simulated orbit and queue subsystem handoffs.",
    callout: "Orbit hold locked, preparing the next sequence.",
  },
  {
    name: "Surface Ops",
    durationSeconds: 900,
    objective: "Run ground operations and staged comm loops.",
    callout: "Surface operations in progress; comms locked.",
  },
  {
    name: "Return & Recovery",
    durationSeconds: 840,
    objective: "Execute return burn, entry corridor checks, and recovery.",
    callout: "Recovery team staged; capsule tracking nominal.",
  },
];

const phaseChecklists: Record<string, string[]> = {
  "Systems Warmup": [
    "Verify control room loops are synchronized.",
    "Confirm simulation telemetry and status buses are live.",
    "Load guidance targets and validate sensor alignment.",
  ],
  "Final Sync": [
    "Poll critical subsystems for final commit.",
    "Load the full mission sequence into the timeline.",
    "Confirm comm routing and handover windows.",
  ],
  "Ignition Run": [
    "Monitor peak-load passage and throttle profile adherence.",
    "Track staged transitions and telemetry packet loss.",
    "Confirm orbit insertion solution locked.",
  ],
  "Trajectory Burn": [
    "Verify burn start/stop markers against call-up.",
    "Update correction windows in the guidance table.",
    "Confirm antenna deployment command time.",
  ],
  "Orbit Hold": [
    "Poll orbit insertion status and delta-v residuals.",
    "Review descent alignment checklist with systems.",
    "Update surface operations timeline for next pass.",
  ],
  "Surface Ops": [
    "Confirm operator telemetry trending nominal.",
    "Log surface task targets and return priorities.",
    "Schedule comms blackout expectations for the pass.",
  ],
  "Return & Recovery": [
    "Verify return burn delta-v achieved.",
    "Review re-entry corridor and blackout timing.",
    "Confirm recovery asset positions and splashdown window.",
  ],
};

const missionEvents: MissionEvent[] = [
  {
    timeSeconds: 60,
    role: "Control",
    label: "Loop Sync",
    detail: "Primary loops aligned; console audio levels matched.",
  },
  {
    timeSeconds: 300,
    role: "Systems",
    label: "Power Grid",
    detail: "Battery and capacitor banks balanced; draw nominal.",
  },
  {
    timeSeconds: 720,
    role: "Dynamics",
    label: "Peak Load",
    detail: "Stress envelope cleared; structural loads steady.",
  },
  {
    timeSeconds: 1020,
    role: "Guidance",
    label: "Orbit Insert",
    detail: "Target orbit achieved; guidance switching to coast.",
  },
  {
    timeSeconds: 1500,
    role: "Comms",
    label: "Long Burn",
    detail: "Ignition confirmed; comms loop remains clear.",
  },
  {
    timeSeconds: 1980,
    role: "Systems",
    label: "Orbit Hold",
    detail: "Insertion confirmed; systems configured for descent.",
  },
  {
    timeSeconds: 2520,
    role: "Life Support",
    label: "Surface Ops",
    detail: "Environmental loop steady; surface timeline clear.",
  },
  {
    timeSeconds: 3300,
    role: "Recovery",
    label: "Entry Interface",
    detail: "Entry corridor aligned; comms blackout expected.",
  },
];

const subsystemStatuses: SubsystemStatus[] = [
  {
    name: "Guidance",
    status: "GO",
    detail: "Alignment passes nominal.",
  },
  {
    name: "Propulsion",
    status: "GO",
    detail: "Pressure bands within simulated tolerance.",
  },
  {
    name: "Life Support",
    status: "GO",
    detail: "Environmental control loops stable.",
  },
  {
    name: "Telemetry",
    status: "GO",
    detail: "Downlink lock solid; redundancy verified.",
  },
  {
    name: "Comms",
    status: "STANDBY",
    detail: "Handover pass scheduled for next phase.",
  },
  {
    name: "Flight Dynamics",
    status: "GO",
    detail: "Trajectory dispersions within corridor.",
  },
  {
    name: "Recovery",
    status: "STANDBY",
    detail: "Recovery assets staged in the window.",
  },
];

const simulationRates = [
  { label: "1x", value: "1" },
  { label: "5x", value: "5" },
  { label: "20x", value: "20" },
];

const simulationScenarios = [
  { label: "Nominal", value: "nominal" },
  { label: "Comms Fade", value: "comms" },
  { label: "Life Support Drift", value: "support" },
  { label: "Guidance Dispersions", value: "guidance" },
];

const scenarioBriefs: Record<string, string> = {
  nominal: "Nominal mission flow with standard callouts and telemetry.",
  comms: "Simulate brief comms dropouts during handover windows.",
  support: "Inject environmental control drift requiring operator guidance.",
  guidance: "Add minor trajectory dispersions to rehearse correction calls.",
};

function formatElapsed(seconds: number) {
  const clamped = Math.max(0, seconds);
  const hrs = Math.floor(clamped / 3600);
  const mins = Math.floor((clamped % 3600) / 60);
  const secs = Math.floor(clamped % 60);
  const padded = [hrs, mins, secs].map((value) =>
    String(value).padStart(2, "0"),
  );
  return padded.join(":");
}

function getPhaseIndex(elapsedSeconds: number) {
  let tally = 0;
  for (let index = 0; index < missionPhases.length; index += 1) {
    tally += missionPhases[index].durationSeconds;
    if (elapsedSeconds < tally) {
      return index;
    }
  }
  return missionPhases.length - 1;
}

function MissionControlPage() {
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [isRunning, setIsRunning] = useState(false);
  const [rate, setRate] = useState("5");
  const [scenario, setScenario] = useState("nominal");

  const totalDuration = useMemo(
    () =>
      missionPhases.reduce((total, phase) => total + phase.durationSeconds, 0),
    [],
  );

  const currentPhaseIndex = getPhaseIndex(elapsedSeconds);
  const currentPhase = missionPhases[currentPhaseIndex];

  useEffect(() => {
    if (!isRunning) {
      return undefined;
    }

    const tickMs = 1000 / Number(rate);
    const interval = window.setInterval(() => {
      setElapsedSeconds((prev) => {
        const next = prev + 1;
        if (next >= totalDuration) {
          window.clearInterval(interval);
          setIsRunning(false);
          return totalDuration;
        }
        return next;
      });
    }, tickMs);

    return () => window.clearInterval(interval);
  }, [isRunning, rate, totalDuration]);

  const progress = Math.min(1, elapsedSeconds / totalDuration);
  const missionTime = formatElapsed(elapsedSeconds);

  const goStatusCount = subsystemStatuses.filter(
    (item) => item.status === "GO",
  ).length;
  const checklistItems = phaseChecklists[currentPhase.name] ?? [];
  const recentEvents = missionEvents
    .filter((event) => event.timeSeconds <= elapsedSeconds)
    .slice(-6);
  const nextEvent = missionEvents.find(
    (event) => event.timeSeconds > elapsedSeconds,
  );

  return (
    <PageFrame>
      <section className="grid gap-6 xl:grid-cols-[1.12fr_0.88fr]">
        <PaperCard className="flex flex-col gap-6">
          <SectionHeader
            eyebrow="Mission Control / Houston Mono"
            title="Mission Simulation Console"
            description="Monitor mission health, advance the timeline, and rehearse the complete mission loop inside a specimen-like control room sheet."
            aside={
              <div className="flex flex-wrap gap-2">
                <SpecChip>{currentPhase.name}</SpecChip>
                <SpecChip tone="muted">
                  {
                    simulationScenarios.find(
                      (option) => option.value === scenario,
                    )?.label
                  }
                </SpecChip>
              </div>
            }
          />
          <div className="grid gap-4 md:grid-cols-3">
            <div className="border-border bg-background/75 border p-4">
              <p className="usgc-kicker">MET</p>
              <p className="font-tomorrow mt-3 text-3xl tracking-[0.12em] tabular-nums">
                {missionTime}
              </p>
              <p className="text-muted-foreground mt-2 font-mono text-[0.68rem] tracking-[0.18em] uppercase">
                Mission elapsed time
              </p>
            </div>
            <div className="border-border bg-background/75 border p-4">
              <p className="usgc-kicker">Phase</p>
              <p className="font-tomorrow mt-3 text-3xl tracking-[0.12em]">
                {currentPhaseIndex + 1}
              </p>
              <p className="text-muted-foreground mt-2 font-mono text-[0.68rem] tracking-[0.18em] uppercase">
                {currentPhase.name}
              </p>
            </div>
            <div className="border-border bg-background/75 border p-4">
              <p className="usgc-kicker">Scenario</p>
              <p className="font-tomorrow mt-3 text-3xl tracking-[0.12em]">
                {rate}x
              </p>
              <p className="text-muted-foreground mt-2 font-mono text-[0.68rem] tracking-[0.18em] uppercase">
                Playback rate
              </p>
            </div>
          </div>
        </PaperCard>

        <TechnicalCard className="flex flex-col gap-5">
          <SectionHeader
            eyebrow="TR-100 Machine Report"
            title="Simulation Summary"
            invert
            aside={
              <SpecChip tone="dark">
                {goStatusCount}/{subsystemStatuses.length} GO
              </SpecChip>
            }
          />
          <div className="space-y-1 font-mono text-sm">
            <DataRow
              label="Scenario"
              value={
                simulationScenarios.find((option) => option.value === scenario)
                  ?.label ?? scenario
              }
            />
            <DataRow
              label="Timeline"
              value={`${currentPhaseIndex + 1}/${missionPhases.length}`}
            />
            <DataRow label="Callout" value={currentPhase.callout} />
            <DataRow
              label="Next Event"
              value={
                nextEvent
                  ? `${formatElapsed(nextEvent.timeSeconds)} · ${nextEvent.label}`
                  : "Mission events complete"
              }
            />
          </div>
          <div className="grid gap-4">
            <MeterBar
              label="Mission Progress"
              value={progress * 100}
              valueLabel={`${(progress * 100).toFixed(0)}%`}
            />
            <MeterBar
              label="Green Systems"
              value={goStatusCount}
              max={subsystemStatuses.length}
              valueLabel={`${goStatusCount}/${subsystemStatuses.length}`}
            />
          </div>
        </TechnicalCard>
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.24fr_0.76fr]">
        <div className="flex flex-col gap-6">
          <PaperCard className="flex flex-col gap-5">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="space-y-2">
                <p className="usgc-kicker">Mission Timeline</p>
                <h2 className="font-tomorrow text-2xl tracking-[0.1em]">
                  Phase Sequencer
                </h2>
              </div>
              <SpecChip tone="muted">
                Total {formatElapsed(totalDuration)}
              </SpecChip>
            </div>
            <MeterBar
              label="Elapsed"
              value={progress * 100}
              valueLabel={missionTime}
            />
            <div className="space-y-3">
              {missionPhases.map((phase, index) => {
                const isActive = index === currentPhaseIndex;
                const isComplete = index < currentPhaseIndex;

                return (
                  <div
                    key={phase.name}
                    className={`border px-4 py-3 transition ${
                      isActive
                        ? "border-border bg-primary/25"
                        : isComplete
                          ? "border-border bg-background/90"
                          : "border-border/70 bg-background/60"
                    }`}
                  >
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div className="flex items-center gap-3">
                        <span
                          className={`font-mono text-[0.68rem] tracking-[0.18em] uppercase ${
                            isComplete
                              ? "text-emerald-500"
                              : isActive
                                ? "text-foreground"
                                : "text-muted-foreground"
                          }`}
                        >
                          {isComplete
                            ? "Complete"
                            : isActive
                              ? "Active"
                              : "Queued"}
                        </span>
                        <span className="font-tomorrow text-lg tracking-[0.06em]">
                          {phase.name}
                        </span>
                      </div>
                      <span className="text-muted-foreground font-mono text-[0.72rem] tracking-[0.18em] uppercase">
                        {formatElapsed(phase.durationSeconds)}
                      </span>
                    </div>
                    <p className="text-muted-foreground mt-2 text-sm leading-6">
                      {phase.objective}
                    </p>
                  </div>
                );
              })}
            </div>
          </PaperCard>

          <PaperCard className="flex flex-col gap-5">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="space-y-2">
                <p className="usgc-kicker">Simulation Console</p>
                <h2 className="font-tomorrow text-2xl tracking-[0.1em]">
                  Mission Playback
                </h2>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button
                  type="button"
                  size="sm"
                  onClick={() => setIsRunning(true)}
                  disabled={isRunning}
                >
                  <Play className="mr-2 h-4 w-4" />
                  Run
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setIsRunning(false)}
                  disabled={!isRunning}
                >
                  <Pause className="mr-2 h-4 w-4" />
                  Pause
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={() => {
                    setElapsedSeconds(0);
                    setIsRunning(false);
                  }}
                >
                  <RotateCcw className="mr-2 h-4 w-4" />
                  Reset
                </Button>
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-[1.18fr_0.82fr]">
              <div className="border-border bg-background/80 border p-4">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-muted-foreground font-mono text-[0.68rem] tracking-[0.18em] uppercase">
                    Active Callout
                  </span>
                  <span className="text-muted-foreground font-mono text-[0.68rem] tracking-[0.18em] uppercase">
                    MET {missionTime}
                  </span>
                </div>
                <p className="font-tomorrow mt-4 text-xl tracking-[0.06em]">
                  {currentPhase.callout}
                </p>
                <p className="text-muted-foreground mt-3 text-sm leading-6">
                  {currentPhase.objective}
                </p>
              </div>

              <div className="grid gap-4">
                <div className="border-border bg-background/80 border p-4">
                  <p className="usgc-kicker">Simulation Rate</p>
                  <ToggleGroup
                    type="single"
                    value={rate}
                    onValueChange={(value) => value && setRate(value)}
                    variant="outline"
                    className="mt-4 justify-start"
                  >
                    {simulationRates.map((speed) => (
                      <ToggleGroupItem key={speed.value} value={speed.value}>
                        {speed.label}
                      </ToggleGroupItem>
                    ))}
                  </ToggleGroup>
                </div>

                <div className="border-border bg-background/80 border p-4">
                  <p className="usgc-kicker">Scenario Deck</p>
                  <ToggleGroup
                    type="single"
                    value={scenario}
                    onValueChange={(value) => value && setScenario(value)}
                    variant="outline"
                    className="mt-4 flex-wrap justify-start"
                  >
                    {simulationScenarios.map((option) => (
                      <ToggleGroupItem key={option.value} value={option.value}>
                        {option.label}
                      </ToggleGroupItem>
                    ))}
                  </ToggleGroup>
                  <p className="text-muted-foreground mt-4 text-sm leading-6">
                    {scenarioBriefs[scenario]}
                  </p>
                </div>
              </div>
            </div>
          </PaperCard>

          <TechnicalCard className="flex flex-col gap-5">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="space-y-2">
                <p className="usgc-kicker text-[#bdb3a6]">Control Room Loop</p>
                <h2 className="font-tomorrow text-2xl tracking-[0.1em] text-[#f6efe6]">
                  Ambient Event Console
                </h2>
              </div>
              <p className="font-mono text-[0.72rem] tracking-[0.18em] text-[#bdb3a6] uppercase">
                {nextEvent
                  ? `Next ${formatElapsed(nextEvent.timeSeconds)}`
                  : "Event stream complete"}
              </p>
            </div>
            <div className="space-y-3">
              {recentEvents.length === 0 ? (
                <p className="font-mono text-sm tracking-[0.16em] text-[#bdb3a6] uppercase">
                  Awaiting timeline start. Event feed will populate once the
                  simulation runs.
                </p>
              ) : (
                recentEvents.map((event) => (
                  <div
                    key={`${event.timeSeconds}-${event.label}`}
                    className="border border-white/20 bg-white/5 px-4 py-3"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <span className="font-mono text-[0.68rem] tracking-[0.18em] text-[#bdb3a6] uppercase">
                        {event.role} · {formatElapsed(event.timeSeconds)}
                      </span>
                      <span className="font-mono text-[0.68rem] tracking-[0.18em] text-[#bdb3a6] uppercase">
                        {event.label}
                      </span>
                    </div>
                    <p className="mt-2 text-sm leading-6 text-[#f6efe6]">
                      {event.detail}
                    </p>
                  </div>
                ))
              )}
            </div>
          </TechnicalCard>
        </div>

        <div className="flex flex-col gap-6">
          <TechnicalCard className="flex flex-col gap-5">
            <div className="flex items-center justify-between gap-3">
              <div className="space-y-2">
                <p className="usgc-kicker text-[#bdb3a6]">Status Matrix</p>
                <h2 className="font-tomorrow text-2xl tracking-[0.1em] text-[#f6efe6]">
                  Subsystem Confidence
                </h2>
              </div>
              <SpecChip tone="dark">{goStatusCount} Green</SpecChip>
            </div>
            <div className="space-y-3">
              {subsystemStatuses.map((system) => (
                <div
                  key={system.name}
                  className="border border-white/20 bg-white/5 px-4 py-3"
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-3">
                      {system.status === "GO" ? (
                        <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                      ) : (
                        <TriangleAlert className="h-4 w-4 text-amber-400" />
                      )}
                      <span className="font-tomorrow text-lg tracking-[0.06em] text-[#f6efe6]">
                        {system.name}
                      </span>
                    </div>
                    <span
                      className={`font-mono text-[0.68rem] tracking-[0.18em] uppercase ${
                        system.status === "GO"
                          ? "text-emerald-400"
                          : system.status === "NO GO"
                            ? "text-red-400"
                            : "text-amber-400"
                      }`}
                    >
                      {system.status}
                    </span>
                  </div>
                  <p className="mt-2 text-sm leading-6 text-[#d8cfc1]">
                    {system.detail}
                  </p>
                </div>
              ))}
            </div>
          </TechnicalCard>

          <PaperCard className="flex flex-col gap-4">
            <div className="space-y-2">
              <p className="usgc-kicker">Telemetry Loop</p>
              <h2 className="font-tomorrow text-2xl tracking-[0.1em]">
                Systems Snapshot
              </h2>
            </div>
            <div className="grid gap-3">
              <div className="border-border bg-background/80 border px-4 py-3">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-muted-foreground font-mono text-[0.68rem] tracking-[0.18em] uppercase">
                    Cabin Pressure
                  </span>
                  <span className="font-tomorrow text-lg tracking-[0.08em]">
                    5.2 psi
                  </span>
                </div>
                <p className="text-muted-foreground mt-2 text-sm">
                  Suit loop maintaining nominal range.
                </p>
              </div>
              <div className="border-border bg-background/80 border px-4 py-3">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-muted-foreground font-mono text-[0.68rem] tracking-[0.18em] uppercase">
                    Battery Load
                  </span>
                  <span className="font-tomorrow text-lg tracking-[0.08em]">
                    74%
                  </span>
                </div>
                <p className="text-muted-foreground mt-2 text-sm">
                  Power budget balanced for current phase.
                </p>
              </div>
              <div className="border-border bg-background/80 border px-4 py-3">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-muted-foreground font-mono text-[0.68rem] tracking-[0.18em] uppercase">
                    High Gain Lock
                  </span>
                  <span className="font-tomorrow text-lg tracking-[0.08em]">
                    Stable
                  </span>
                </div>
                <p className="text-muted-foreground mt-2 text-sm">
                  Deep-space tracking aligned with relay.
                </p>
              </div>
              <div className="border-border bg-background/80 border px-4 py-3">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-muted-foreground font-mono text-[0.68rem] tracking-[0.18em] uppercase">
                    Surface Ops
                  </span>
                  <span className="font-tomorrow text-lg tracking-[0.08em]">
                    Ready
                  </span>
                </div>
                <p className="text-muted-foreground mt-2 text-sm">
                  EVA timeline pre-brief complete.
                </p>
              </div>
            </div>
          </PaperCard>

          <PaperCard className="flex flex-col gap-4">
            <div className="space-y-2">
              <p className="usgc-kicker">Flight Plan</p>
              <h2 className="font-tomorrow text-2xl tracking-[0.1em]">
                Phase Runbook
              </h2>
              <p className="text-muted-foreground text-sm">
                Active phase cues for {currentPhase.name}.
              </p>
            </div>
            <div className="space-y-2">
              {checklistItems.map((item) => (
                <div
                  key={item}
                  className="border-border bg-background/80 border px-4 py-3"
                >
                  <p className="text-muted-foreground text-sm leading-6">
                    {item}
                  </p>
                </div>
              ))}
            </div>
          </PaperCard>
        </div>
      </section>
    </PageFrame>
  );
}

export const Route = createFileRoute("/mission-control/")({
  component: MissionControlPage,
});
