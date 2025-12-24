import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import {
  ToggleGroup,
  ToggleGroupItem,
} from "@/components/ui/toggle-group";
import { createFileRoute } from "@tanstack/react-router";
import { CheckCircle2, Pause, Play, RotateCcw, TriangleAlert } from "lucide-react";
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
  const padded = [hrs, mins, secs].map((value) => String(value).padStart(2, "0"));
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
    () => missionPhases.reduce((total, phase) => total + phase.durationSeconds, 0),
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

  const goStatusCount = subsystemStatuses.filter((item) => item.status === "GO").length;
  const checklistItems = phaseChecklists[currentPhase.name] ?? [];
  const recentEvents = missionEvents.filter((event) => event.timeSeconds <= elapsedSeconds).slice(-6);
  const nextEvent = missionEvents.find((event) => event.timeSeconds > elapsedSeconds);

  return (
    <div className="flex h-full flex-col gap-4 text-foreground">
      <header className="flex flex-wrap items-center justify-between gap-4 rounded-lg border border-border bg-card px-6 py-4">
        <div className="space-y-1">
          <p className="text-xs font-tomorrow uppercase text-muted-foreground">Control Room Simulation</p>
          <h1 className="text-2xl font-semibold tracking-tight">Mission Simulation Console</h1>
          <p className="text-sm text-muted-foreground">
            Monitor mission health, advance the timeline, and rehearse the complete mission loop.
          </p>
        </div>
        <div className="flex flex-col items-end gap-2 rounded-md border border-border bg-background px-4 py-3">
          <span className="text-xs font-tomorrow uppercase text-muted-foreground">Mission Elapsed Time</span>
          <span className="text-2xl font-semibold tabular-nums">{missionTime}</span>
          <span className="text-xs text-muted-foreground">Phase: {currentPhase.name}</span>
        </div>
      </header>

      <section className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
        <div className="space-y-4">
          <div className="rounded-lg border border-border bg-card p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-xs font-tomorrow uppercase text-muted-foreground">Mission Timeline</p>
                <h2 className="text-lg font-semibold">Phase Sequencer</h2>
              </div>
              <div className="text-xs text-muted-foreground">Total Duration: {formatElapsed(totalDuration)}</div>
            </div>
            <div className="mt-4">
              <div className="h-2 w-full rounded-full bg-muted">
                <div
                  className="h-2 rounded-full bg-primary transition-all"
                  style={{ width: `${progress * 100}%` }}
                />
              </div>
              <div className="mt-4 space-y-3">
                {missionPhases.map((phase, index) => {
                  const isActive = index === currentPhaseIndex;
                  const isComplete = index < currentPhaseIndex;
                  return (
                  <div
                    key={phase.name}
                    className={`rounded-md border px-3 py-2 transition ${
                        isActive
                          ? "border-primary/70 bg-primary/10"
                          : "border-border bg-background"
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <span
                            className={`text-xs font-tomorrow uppercase ${
                              isComplete
                                ? "text-emerald-400"
                                : isActive
                                  ? "text-primary"
                                  : "text-muted-foreground"
                            }`}
                          >
                            {isComplete ? "Complete" : isActive ? "Active" : "Queued"}
                          </span>
                          <span className="text-sm font-semibold">{phase.name}</span>
                        </div>
                        <span className="text-xs text-muted-foreground">{formatElapsed(phase.durationSeconds)}</span>
                      </div>
                      <p className="mt-1 text-xs text-muted-foreground">{phase.objective}</p>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          <div className="rounded-lg border border-border bg-card p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="text-xs font-tomorrow uppercase text-muted-foreground">Simulation Console</p>
                <h2 className="text-lg font-semibold">Mission Playback</h2>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  size="sm"
                  onClick={() => setIsRunning(true)}
                  disabled={isRunning}
                >
                  <Play className="mr-2 h-4 w-4" />
                  Run Simulation
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
            <Separator className="my-4" />
            <div className="grid gap-4 md:grid-cols-[1.2fr_1fr]">
              <div className="space-y-3 rounded-md border border-border bg-background p-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-tomorrow uppercase text-muted-foreground">Active Callout</span>
                  <span className="text-xs text-muted-foreground">MET {missionTime}</span>
                </div>
                <p className="text-sm font-semibold">{currentPhase.callout}</p>
                <p className="text-xs text-muted-foreground">{currentPhase.objective}</p>
              </div>
              <div className="space-y-2">
                <p className="text-xs font-tomorrow uppercase text-muted-foreground">Simulation Rate</p>
                <ToggleGroup
                  type="single"
                  value={rate}
                  onValueChange={(value) => value && setRate(value)}
                  className="justify-start"
                >
                  {simulationRates.map((speed) => (
                    <ToggleGroupItem key={speed.value} value={speed.value}>
                      {speed.label}
                    </ToggleGroupItem>
                  ))}
                </ToggleGroup>
                <p className="text-xs text-muted-foreground">
                  Adjust the playback speed to rehearse the full mission timeline.
                </p>
              </div>
            </div>
            <div className="mt-4 space-y-2 rounded-md border border-border bg-background p-3">
              <p className="text-xs font-tomorrow uppercase text-muted-foreground">Scenario Deck</p>
              <ToggleGroup
                type="single"
                value={scenario}
                onValueChange={(value) => value && setScenario(value)}
                className="justify-start"
              >
                {simulationScenarios.map((option) => (
                  <ToggleGroupItem key={option.value} value={option.value}>
                    {option.label}
                  </ToggleGroupItem>
                ))}
              </ToggleGroup>
              <p className="text-xs text-muted-foreground">{scenarioBriefs[scenario]}</p>
            </div>
          </div>

          <div className="rounded-lg border border-border bg-card p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="text-xs font-tomorrow uppercase text-muted-foreground">Control Room Loop</p>
                <h2 className="text-lg font-semibold">Ambient Event Console</h2>
              </div>
              {nextEvent ? (
                <div className="text-xs text-muted-foreground">
                  Next: {formatElapsed(nextEvent.timeSeconds)} · {nextEvent.label}
                </div>
              ) : (
                <div className="text-xs text-muted-foreground">Mission events complete</div>
              )}
            </div>
            <Separator className="my-4" />
            <div className="space-y-3">
              {recentEvents.length === 0 ? (
                <p className="text-xs text-muted-foreground">
                  Awaiting timeline start. Event feed will populate once the simulation runs.
                </p>
              ) : (
                recentEvents.map((event) => (
                  <div key={`${event.timeSeconds}-${event.label}`} className="rounded-md border border-border bg-background px-3 py-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-tomorrow uppercase text-muted-foreground">
                        {event.role} · {formatElapsed(event.timeSeconds)}
                      </span>
                      <span className="text-xs text-muted-foreground">{event.label}</span>
                    </div>
                    <p className="mt-1 text-sm font-semibold">{event.detail}</p>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        <div className="space-y-4">
          <div className="rounded-lg border border-border bg-card p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-tomorrow uppercase text-muted-foreground">Status Matrix</p>
                <h2 className="text-lg font-semibold">Subsystem Confidence</h2>
              </div>
              <div className="text-xs text-muted-foreground">
                {goStatusCount}/{subsystemStatuses.length} systems green
              </div>
            </div>
            <div className="mt-4 space-y-3">
              {subsystemStatuses.map((system) => (
                <div key={system.name} className="rounded-md border border-border bg-background px-3 py-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      {system.status === "GO" ? (
                        <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                      ) : (
                        <TriangleAlert className="h-4 w-4 text-amber-400" />
                      )}
                      <span className="text-sm font-semibold">{system.name}</span>
                    </div>
                    <span
                      className={`text-xs font-tomorrow uppercase ${
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
                  <p className="mt-1 text-xs text-muted-foreground">{system.detail}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-lg border border-border bg-card p-4">
            <p className="text-xs font-tomorrow uppercase text-muted-foreground">Telemetry Loop</p>
            <h2 className="text-lg font-semibold">Systems Snapshot</h2>
            <div className="mt-4 grid gap-3">
              <div className="rounded-md border border-border bg-background px-3 py-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-tomorrow uppercase text-muted-foreground">Cabin Pressure</span>
                  <span className="text-sm font-semibold">5.2 psi</span>
                </div>
                <p className="text-xs text-muted-foreground">Suit loop maintaining nominal range.</p>
              </div>
              <div className="rounded-md border border-border bg-background px-3 py-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-tomorrow uppercase text-muted-foreground">Battery Load</span>
                  <span className="text-sm font-semibold">74%</span>
                </div>
                <p className="text-xs text-muted-foreground">Power budget balanced for current phase.</p>
              </div>
              <div className="rounded-md border border-border bg-background px-3 py-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-tomorrow uppercase text-muted-foreground">High Gain Lock</span>
                  <span className="text-sm font-semibold">Stable</span>
                </div>
                <p className="text-xs text-muted-foreground">Deep-space tracking aligned with relay.</p>
              </div>
              <div className="rounded-md border border-border bg-background px-3 py-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-tomorrow uppercase text-muted-foreground">Surface Ops</span>
                  <span className="text-sm font-semibold">Ready</span>
                </div>
                <p className="text-xs text-muted-foreground">EVA timeline pre-brief complete.</p>
              </div>
            </div>
          </div>

          <div className="rounded-lg border border-border bg-card p-4">
            <p className="text-xs font-tomorrow uppercase text-muted-foreground">Flight Plan</p>
            <h2 className="text-lg font-semibold">Phase Runbook</h2>
            <p className="mt-1 text-xs text-muted-foreground">
              Active phase cues for {currentPhase.name}.
            </p>
            <div className="mt-4 space-y-2">
              {checklistItems.map((item) => (
                <div key={item} className="rounded-md border border-border bg-background px-3 py-2">
                  <p className="text-xs text-muted-foreground">{item}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

export const Route = createFileRoute("/mission-control/")({
  component: MissionControlPage,
});
