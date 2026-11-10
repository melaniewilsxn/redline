import type { ReactNode } from "react";

import styles from "./toast.module.css";

/**
 * A short confirmation that hides on its own.
 * @param message - What just happened.
 * @returns The toast.
 * @throws Does not throw.
 */
export function Toast({ message }: { message: string }): ReactNode {
  return (
    <div className={styles.toast} role="status" aria-live="polite">
      {message}
    </div>
  );
}
