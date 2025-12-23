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

const missionPhases: MissionPhase[] = [
  {
    name: "Pre-Launch",
    durationSeconds: 420,
    objective: "Vehicle power-up and integrated systems checks.",
    callout: "All stations confirm readiness for terminal count.",
  },
  {
    name: "Terminal Count",
    durationSeconds: 600,
    objective: "Guidance alignment, range clearance, and propellant load.",
    callout: "Guidance, flight, and booster are green across the board.",
  },
  {
    name: "Launch + Ascent",
    durationSeconds: 780,
    objective: "Lift-off through staging and orbital insertion burn.",
    callout: "We have liftoff, tracking through max-Q and staging.",
  },
  {
    name: "Translunar Injection",
    durationSeconds: 540,
    objective: "Execute injection burn and configure navigation updates.",
    callout: "Trajectory looks tight; onboard navigation synced.",
  },
  {
    name: "Lunar Orbit",
    durationSeconds: 720,
    objective: "Orbit insertion and surface operations staging.",
    callout: "Orbit stable; prepare for descent timeline review.",
  },
  {
    name: "Surface Ops",
    durationSeconds: 900,
    objective: "Simulated EVA, sample collection, and comm loops.",
    callout: "Surface EVA complete; samples secured.",
  },
  {
    name: "Return & Recovery",
    durationSeconds: 840,
    objective: "Trans-Earth injection, entry corridor, and splashdown.",
    callout: "Recovery forces standing by; capsule tracking nominal.",
  },
];

const subsystemStatuses: SubsystemStatus[] = [
  {
    name: "Guidance",
    status: "GO",
    detail: "IMU aligned and nav star checks nominal.",
  },
  {
    name: "Propulsion",
    status: "GO",
    detail: "Chamber pressures within simulated tolerance.",
  },
  {
    name: "EECOM",
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
    detail: "High-gain antenna pass scheduled for next phase.",
  },
  {
    name: "Flight Dynamics",
    status: "GO",
    detail: "Trajectory dispersions well within corridor.",
  },
  {
    name: "Recovery",
    status: "STANDBY",
    detail: "Splashdown assets staged in the Pacific box.",
  },
];

const simulationRates = [
  { label: "1x", value: "1" },
  { label: "5x", value: "5" },
  { label: "20x", value: "20" },
];

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

  return (
    <div className="flex h-full flex-col gap-4 text-foreground">
      <header className="flex flex-wrap items-center justify-between gap-4 rounded-lg border border-border bg-card px-6 py-4">
        <div className="space-y-1">
          <p className="text-xs font-tomorrow uppercase text-muted-foreground">Apollo Simulation Control</p>
          <h1 className="text-2xl font-semibold tracking-tight">Mission Control Operations</h1>
          <p className="text-sm text-muted-foreground">
            Monitor mission health, advance the timeline, and run a full-flight simulation from launch to recovery.
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
          </div>
        </div>

        <div className="space-y-4">
          <div className="rounded-lg border border-border bg-card p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-tomorrow uppercase text-muted-foreground">Flight Director</p>
                <h2 className="text-lg font-semibold">Go/No-Go Poll</h2>
              </div>
              <div className="text-xs text-muted-foreground">
                {goStatusCount}/{subsystemStatuses.length} stations GO
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
        </div>
      </section>
    </div>
  );
}

export const Route = createFileRoute("/mission-control/")({
  component: MissionControlPage,
});
