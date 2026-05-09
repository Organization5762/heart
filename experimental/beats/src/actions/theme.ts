import { ThemeMode } from "@/types/theme-mode";
import { isElectronRuntime } from "@/utils/runtime";
import { LOCAL_STORAGE_KEYS } from "@/constants";

export interface ThemePreferences {
  system: ThemeMode;
  local: ThemeMode | null;
}

async function getThemeClient() {
  const { ipc } = await import("@/ipc/manager");
  return ipc.client.theme;
}

function getStoredTheme(): ThemeMode | null {
  return localStorage.getItem(LOCAL_STORAGE_KEYS.THEME) as ThemeMode | null;
}

function resolveSystemTheme(): "dark" | "light" {
  if (
    typeof window !== "undefined" &&
    window.matchMedia("(prefers-color-scheme: dark)").matches
  ) {
    return "dark";
  }

  return "light";
}

function resolveDarkMode(mode: ThemeMode): boolean {
  if (mode === "system") {
    return resolveSystemTheme() === "dark";
  }

  return mode === "dark";
}

export async function getCurrentTheme(): Promise<ThemePreferences> {
  const currentTheme = isElectronRuntime()
    ? await (await getThemeClient()).getCurrentThemeMode()
    : resolveSystemTheme();
  const localTheme = getStoredTheme();

  return {
    system: currentTheme,
    local: localTheme,
  };
}

export async function setTheme(newTheme: ThemeMode) {
  if (isElectronRuntime()) {
    await (await getThemeClient()).setThemeMode(newTheme);
  }
  localStorage.setItem(LOCAL_STORAGE_KEYS.THEME, newTheme);
  updateDocumentTheme(resolveDarkMode(newTheme));
}

export async function toggleTheme() {
  if (isElectronRuntime()) {
    const isDarkMode = await (await getThemeClient()).toggleThemeMode();
    const newTheme = isDarkMode ? "dark" : "light";

    updateDocumentTheme(isDarkMode);
    localStorage.setItem(LOCAL_STORAGE_KEYS.THEME, newTheme);
    return;
  }

  const newTheme = document.documentElement.classList.contains("dark")
    ? "light"
    : "dark";
  updateDocumentTheme(newTheme === "dark");
  localStorage.setItem(LOCAL_STORAGE_KEYS.THEME, newTheme);
}

export async function syncWithLocalTheme() {
  const { local } = await getCurrentTheme();
  if (!local) {
    await setTheme("system");
    return;
  }

  await setTheme(local);
}

function updateDocumentTheme(isDarkMode: boolean) {
  if (isDarkMode) {
    document.documentElement.classList.add("dark");
  } else {
    document.documentElement.classList.remove("dark");
  }
}
