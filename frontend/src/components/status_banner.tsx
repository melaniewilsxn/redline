import type { ReactNode } from "react";

import { Button, ButtonTone, ButtonVariant } from "./button.tsx";
import styles from "./status_banner.module.css";

/**
 * A plain message with one next step.
 * @param message - What went wrong and what to do.
 * @param actionLabel - The next step, or an empty string when there is nothing to press.
 * @param onAction - The next step.
 * @returns The banner.
 * @throws Does not throw.
 */
export function StatusBanner({
  message,
  actionLabel,
  onAction,
}: {
  message: string;
  actionLabel: string;
  onAction: () => void;
}): ReactNode {
  return (
    <div className={styles.banner} role="status">
      <p className={styles.message}>{message}</p>
      {actionLabel === "" ? null : (
        <Button
          variant={ButtonVariant.Secondary}
          tone={ButtonTone.Default}
          label={actionLabel}
          shortcut=""
          disabled={false}
          onClick={onAction}
        />
      )}
    </div>
  );
}
