export function isElectronRuntime(): boolean {
  if (typeof navigator === "undefined") {
    return false;
  }

  return navigator.userAgent.includes("Electron");
}
