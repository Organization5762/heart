import { isElectronRuntime } from "@/utils/runtime";

async function getIpcClient() {
  const { ipc } = await import("@/ipc/manager");
  return ipc.client;
}

export async function getPlatform() {
  if (isElectronRuntime()) {
    const client = await getIpcClient();
    return client.app.currentPlatfom();
  }

  if (typeof navigator !== "undefined" && navigator.platform) {
    return navigator.platform;
  }

  return "web";
}

export async function getAppVersion() {
  if (isElectronRuntime()) {
    const client = await getIpcClient();
    return client.app.appVersion();
  }

  return import.meta.env.VITE_BEATS_APP_VERSION?.trim() || "web";
}
