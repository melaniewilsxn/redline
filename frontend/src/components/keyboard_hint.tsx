import type { ReactNode } from "react";

import styles from "./keyboard_hint.module.css";

/**
 * A small chip naming a keyboard shortcut.
 * @param keys - The keys to show, such as J or ⌘ Enter.
 * @returns The chip.
 * @throws Does not throw.
 */
export function KeyboardHint({ keys }: { keys: string }): ReactNode {
  return <kbd className={styles.hint}>{keys}</kbd>;
}
