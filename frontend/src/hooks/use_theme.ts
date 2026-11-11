import { useCallback, useState } from "react";

export const ThemeChoice = {
  Light: "light",
  Dark: "dark",
} as const;
export type ThemeChoice = (typeof ThemeChoice)[keyof typeof ThemeChoice];

const THEME_STORAGE_KEY = "redline-theme";

/**
 * Read the stored theme, falling back to light.
 * @returns The stored choice.
 * @throws Does not throw.
 */
function readStoredTheme(): ThemeChoice {
  try {
    const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
    if (stored === ThemeChoice.Dark) {
      return ThemeChoice.Dark;
    }
    return ThemeChoice.Light;
  } catch {
    return ThemeChoice.Light;
  }
}

/**
 * Apply a theme choice to the document element.
 * @param theme - The choice to show.
 * @throws Does not throw.
 */
function applyTheme(theme: ThemeChoice): void {
  document.documentElement.dataset.theme = theme;
}

/**
 * Remember a theme choice. A failed write leaves the current appearance in place.
 * @param theme - The choice to store.
 * @throws Does not throw.
 */
function storeTheme(theme: ThemeChoice): void {
  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, theme);
  } catch {
    return;
  }
}

/**
 * Keep the light or dark theme and remember the choice.
 * @returns The current choice and a way to change it.
 * @throws Does not throw.
 */
export function useTheme(): { theme: ThemeChoice; setTheme: (theme: ThemeChoice) => void } {
  const [theme, setThemeState] = useState<ThemeChoice>(readStoredTheme);

  const setTheme = useCallback((nextTheme: ThemeChoice) => {
    applyTheme(nextTheme);
    storeTheme(nextTheme);
    setThemeState(nextTheme);
  }, []);

  return { theme, setTheme };
}
