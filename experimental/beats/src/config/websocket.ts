const EMPTY_WEBSOCKET_URL = "";
const DEFAULT_WEBSOCKET_PORT = "8765";

export const DISABLED_WEBSOCKET_LABEL = "Not configured";

function trimValue(value: string | undefined): string | null {
  const trimmed = value?.trim();
  if (!trimmed || trimmed === EMPTY_WEBSOCKET_URL) {
    return null;
  }

  return trimmed;
}

function getInferredBeatsWebSocketUrl(): string | null {
  if (typeof window === "undefined") {
    return null;
  }

  const host = trimValue(import.meta.env.VITE_BEATS_WEBSOCKET_HOST)
    ?? window.location.hostname;
  if (!host) {
    return null;
  }

  const port = trimValue(import.meta.env.VITE_BEATS_WEBSOCKET_PORT)
    ?? DEFAULT_WEBSOCKET_PORT;
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";

  return `${protocol}://${host}:${port}`;
}

export function getConfiguredBeatsWebSocketUrl(): string | null {
  const configuredUrl = trimValue(import.meta.env.VITE_BEATS_WEBSOCKET_URL);
  if (configuredUrl) {
    return configuredUrl;
  }

  return getInferredBeatsWebSocketUrl();
}
