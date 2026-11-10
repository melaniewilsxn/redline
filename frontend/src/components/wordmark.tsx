import type { ReactNode } from "react";

import styles from "./wordmark.module.css";

/**
 * The Redline wordmark. Choosing it returns to the contract list.
 * @param onSelectHome - Clears the open contract.
 * @returns The wordmark button.
 * @throws Does not throw.
 */
export function Wordmark({ onSelectHome }: { onSelectHome: () => void }): ReactNode {
  return (
    <button type="button" className={styles.wordmark} onClick={onSelectHome}>
      Red<span className={styles.line}>line</span>
    </button>
  );
}
