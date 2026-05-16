export async function getPlatform() {
  if (typeof navigator !== "undefined" && navigator.platform) {
    return navigator.platform;
  }

  return "web";
}

export async function getAppVersion() {
  return import.meta.env.VITE_BEATS_APP_VERSION?.trim() || "web";
}
