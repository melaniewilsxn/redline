import type { ReactNode } from "react";

import { ThemeChoice, type ThemeChoice as ThemeChoiceValue } from "../hooks/use_theme.ts";
import styles from "./theme_toggle.module.css";

const THEME_LABEL: Record<ThemeChoiceValue, string> = {
  [ThemeChoice.Light]: "Theme is light",
  [ThemeChoice.Dark]: "Theme is dark",
};

/**
 * Cycle the theme and show which one is in use.
 * @param theme - The current choice.
 * @param onCycle - Moves to the next choice.
 * @returns The toggle button.
 * @throws Does not throw.
 */
export function ThemeToggle({
  theme,
  onCycle,
}: {
  theme: ThemeChoiceValue;
  onCycle: () => void;
}): ReactNode {
  return (
    <button
      type="button"
      className={styles.toggle}
      aria-label={THEME_LABEL[theme]}
      onClick={onCycle}
    >
      <ThemeIcon theme={theme} />
    </button>
  );
}

/**
 * Draw the icon for the current theme.
 * @param theme - The current choice.
 * @returns The icon.
 * @throws Does not throw.
 */
function ThemeIcon({ theme }: { theme: ThemeChoiceValue }): ReactNode {
  if (theme === ThemeChoice.Dark) {
    return (
      <svg className={styles.icon} viewBox="0 0 16 16" aria-hidden="true">
        <path d="M10 2.2A5.5 5.5 0 1 0 13.8 10 4.2 4.2 0 0 1 10 2.2Z" />
      </svg>
    );
  }
  return (
    <svg className={styles.icon} viewBox="0 0 16 16" aria-hidden="true">
      <circle cx="8" cy="8" r="2.5" />
      <path d="M8 1.5v1.5M8 13v1.5M1.5 8H3M13 8h1.5M3.2 3.2l1.1 1.1M11.7 11.7l1.1 1.1M3.2 12.8l1.1-1.1M11.7 4.3l1.1-1.1" />
    </svg>
  );
}
