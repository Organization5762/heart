import type { usePeripheralEvents } from "@/actions/ws/providers/PeripheralEventsProvider";

const INPUT_DEBUG_STREAM_TAG = "input_debug_stream";
const NAVIGATION_STREAM_NAME = "navigation.intent";
const ACTIVATE_SOURCES = new Set([
  "keyboard.down",
  "gamepad.south",
  "switch.button",
]);
const ALTERNATE_SOURCES = new Set([
  "keyboard.up",
  "gamepad.north",
  "switch.long_button",
]);
const MAX_RECENT_INTENTS = 6;

export type NavigationIntentKind = "browse" | "activate" | "alternate";

export type NavigationIntentSnapshot = {
  kind: NavigationIntentKind;
  source: string;
  step: number;
  ts: number;
};

export type NavigationTelemetrySummary = {
  activateCount: number;
  alternateCount: number;
  browseCount: number;
  inferredModeState: "idle" | "browsing" | "committed" | "select_mode";
  lastCommittedDelta: number;
  lastIntent: NavigationIntentSnapshot | null;
  pendingBrowseOffset: number;
  recentIntents: NavigationIntentSnapshot[];
};

type PeripheralEvent = ReturnType<typeof usePeripheralEvents>[number];

export function summarizeNavigationTelemetry(
  events: PeripheralEvent[],
): NavigationTelemetrySummary {
  const navigationIntents = events
    .filter(isNavigationPeripheralEvent)
    .map((event) => toNavigationIntentSnapshot(event))
    .filter((event): event is NavigationIntentSnapshot => event !== null);

  let pendingBrowseOffset = 0;
  let lastCommittedDelta = 0;
  let inferredModeState: NavigationTelemetrySummary["inferredModeState"] =
    "idle";
  let activateCount = 0;
  let alternateCount = 0;
  let browseCount = 0;

  for (const intent of [...navigationIntents].reverse()) {
    if (intent.kind === "browse") {
      browseCount += 1;
      pendingBrowseOffset += intent.step;
      inferredModeState = "browsing";
      continue;
    }

    if (intent.kind === "activate") {
      activateCount += 1;
      lastCommittedDelta = pendingBrowseOffset;
      pendingBrowseOffset = 0;
      inferredModeState = "committed";
      continue;
    }

    alternateCount += 1;
    pendingBrowseOffset = 0;
    inferredModeState = "select_mode";
  }

  return {
    activateCount,
    alternateCount,
    browseCount,
    inferredModeState,
    lastCommittedDelta,
    lastIntent: navigationIntents[0] ?? null,
    pendingBrowseOffset,
    recentIntents: navigationIntents.slice(0, MAX_RECENT_INTENTS),
  };
}

export function isNavigationPeripheralEvent(event: PeripheralEvent) {
  return (
    tagVariant(
      event.msg.payload.peripheralInfo.tags,
      INPUT_DEBUG_STREAM_TAG,
    ) === NAVIGATION_STREAM_NAME
  );
}

function toNavigationIntentSnapshot(
  event: PeripheralEvent,
): NavigationIntentSnapshot | null {
  const payload = event.msg.payload.data;
  if (!payload || typeof payload !== "object") {
    return null;
  }

  const source =
    readStringField(payload, "source") ??
    readStringField(payload, "source_id") ??
    event.msg.payload.peripheralInfo.id ??
    "unknown";
  const step = readNumberField(payload, "step");

  if (typeof step === "number" && Number.isFinite(step)) {
    return {
      kind: "browse",
      source,
      step,
      ts: event.ts,
    };
  }

  if (ALTERNATE_SOURCES.has(source)) {
    return {
      kind: "alternate",
      source,
      step: 0,
      ts: event.ts,
    };
  }

  if (ACTIVATE_SOURCES.has(source)) {
    return {
      kind: "activate",
      source,
      step: 0,
      ts: event.ts,
    };
  }

  return null;
}

function tagVariant(
  tags: Array<{ name: string; variant: string }>,
  name: string,
): string | null {
  return tags.find((tag) => tag.name === name)?.variant ?? null;
}

function readStringField(input: object, field: string) {
  const value = (input as Record<string, unknown>)[field];
  return typeof value === "string" ? value : null;
}

function readNumberField(input: object, field: string) {
  const value = (input as Record<string, unknown>)[field];
  return typeof value === "number" ? value : null;
}
