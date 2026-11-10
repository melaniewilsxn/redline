import type { ReactNode } from "react";

import { Button, ButtonTone, ButtonVariant } from "../../components/button.tsx";
import styles from "./apply_bar.module.css";

/**
 * Apply the accepted suggestions, or accept them all, or discard the review.
 * @param acceptedCount - How many suggestions are accepted.
 * @param note - A reason the last apply did not run, or an empty string.
 * @param onApply - Applies the accepted suggestions.
 * @param onAcceptAll - Accepts every suggestion that is still pending.
 * @param onDiscard - Closes the review.
 * @returns The bar.
 * @throws Does not throw.
 */
export function ApplyBar({
  acceptedCount,
  note,
  onApply,
  onAcceptAll,
  onDiscard,
}: {
  acceptedCount: number;
  note: string;
  onApply: () => void;
  onAcceptAll: () => void;
  onDiscard: () => void;
}): ReactNode {
  return (
    <div className={styles.bar}>
      <Button
        variant={ButtonVariant.Primary}
        tone={ButtonTone.Default}
        label={applyLabel(acceptedCount)}
        shortcut="⌘ Enter"
        disabled={false}
        onClick={onApply}
      />
      <div className={styles.secondary}>
        <Button
          variant={ButtonVariant.Secondary}
          tone={ButtonTone.Default}
          label="Accept all"
          shortcut=""
          disabled={false}
          onClick={onAcceptAll}
        />
        <Button
          variant={ButtonVariant.Ghost}
          tone={ButtonTone.Default}
          label="Discard review"
          shortcut=""
          disabled={false}
          onClick={onDiscard}
        />
      </div>
      {note === "" ? null : <p className={styles.note}>{note}</p>}
    </div>
  );
}

/**
 * Name the apply action for the accepted count.
 * @param acceptedCount - How many suggestions are accepted.
 * @returns The button label.
 * @throws Does not throw.
 */
function applyLabel(acceptedCount: number): string {
  if (acceptedCount === 1) {
    return "Apply 1 change";
  }
  return `Apply ${acceptedCount} changes`;
}
