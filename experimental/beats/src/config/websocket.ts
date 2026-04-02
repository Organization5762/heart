const EMPTY_WEBSOCKET_URL = "";

export const DISABLED_WEBSOCKET_LABEL = "Not configured";

export function getConfiguredBeatsWebSocketUrl(): string | null {
  const configuredUrl = import.meta.env.VITE_BEATS_WEBSOCKET_URL?.trim();

  if (!configuredUrl || configuredUrl === EMPTY_WEBSOCKET_URL) {
    return null;
  }

  return configuredUrl;
}
