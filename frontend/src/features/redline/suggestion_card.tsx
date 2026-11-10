import type { ReactNode } from "react";

import { Button, ButtonTone, ButtonVariant } from "../../components/button.tsx";
import { SuggestionStatus, type ReviewSuggestion } from "./document_segments.ts";
import styles from "./suggestion_card.module.css";

const TITLE_CHARACTER_LIMIT = 60;

/**
 * One suggestion, with its decision controls.
 * @param suggestion - The suggestion.
 * @param active - Whether the keyboard is on this card.
 * @param onSelect - Makes the card active.
 * @param onHover - Highlights the matching text.
 * @param onAccept - Accepts the suggestion.
 * @param onReject - Rejects the suggestion.
 * @param onUndo - Returns the suggestion to pending.
 * @returns The card.
 * @throws Does not throw.
 */
export function SuggestionCard({
  suggestion,
  active,
  onSelect,
  onHover,
  onAccept,
  onReject,
  onUndo,
}: {
  suggestion: ReviewSuggestion;
  active: boolean;
  onSelect: () => void;
  onHover: (suggestionId: string | null) => void;
  onAccept: () => void;
  onReject: () => void;
  onUndo: () => void;
}): ReactNode {
  const pending = suggestion.status === SuggestionStatus.Pending;
  return (
    <article
      className={active ? `${styles.card} ${styles.active}` : styles.card}
      onMouseEnter={() => onHover(suggestion.suggestionId)}
      onMouseLeave={() => onHover(null)}
      onClick={onSelect}
    >
      <span className={styles.tag}>AI</span>
      <h3 className={styles.title}>{suggestionTitle(suggestion.rationale)}</h3>
      <p className={styles.rationale}>{suggestion.rationale}</p>
      {pending ? (
        <div className={styles.actions}>
          <Button
            variant={ButtonVariant.Secondary}
            tone={ButtonTone.Accept}
            label="Accept"
            shortcut="A"
            disabled={false}
            onClick={onAccept}
          />
          <Button
            variant={ButtonVariant.Secondary}
            tone={ButtonTone.Default}
            label="Reject"
            shortcut="R"
            disabled={false}
            onClick={onReject}
          />
        </div>
      ) : (
        <div className={styles.actions}>
          <p
            className={
              suggestion.status === SuggestionStatus.Accepted
                ? `${styles.decision} ${styles.accepted}`
                : `${styles.decision} ${styles.rejected}`
            }
          >
            {suggestion.status === SuggestionStatus.Accepted ? "Accepted" : "Rejected"}
          </p>
          <Button
            variant={ButtonVariant.Ghost}
            tone={ButtonTone.Default}
            label="Undo"
            shortcut="U"
            disabled={false}
            onClick={onUndo}
          />
        </div>
      )}
    </article>
  );
}

/**
 * Use the first sentence of a rationale, cut on a word before 60 characters.
 * @param rationale - The full reason.
 * @returns The card title.
 * @throws Does not throw.
 */
function suggestionTitle(rationale: string): string {
  const sentenceEnd = rationale.indexOf(".");
  const sentence = sentenceEnd === -1 ? rationale : rationale.slice(0, sentenceEnd);
  if (sentence.length <= TITLE_CHARACTER_LIMIT) {
    return sentence;
  }
  const shortened = sentence.slice(0, TITLE_CHARACTER_LIMIT);
  const lastSpace = shortened.lastIndexOf(" ");
  if (lastSpace === -1) {
    return shortened;
  }
  return shortened.slice(0, lastSpace);
}
