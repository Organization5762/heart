import { ThemeMode } from "@/types/theme-mode";
import { LOCAL_STORAGE_KEYS } from "@/constants";

export interface ThemePreferences {
  system: ThemeMode;
  local: ThemeMode | null;
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
  const currentTheme = resolveSystemTheme();
  const localTheme = getStoredTheme();

  return {
    system: currentTheme,
    local: localTheme,
  };
}

export async function setTheme(newTheme: ThemeMode) {
  localStorage.setItem(LOCAL_STORAGE_KEYS.THEME, newTheme);
  updateDocumentTheme(resolveDarkMode(newTheme));
}

export async function toggleTheme() {
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
