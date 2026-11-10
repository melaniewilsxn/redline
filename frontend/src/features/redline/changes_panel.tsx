import type { ReactNode } from "react";

import { ApiError } from "../../api/client.ts";
import { ApiErrorType, type DroppedSuggestionResponse } from "../../api/types.ts";
import { KeyboardHint } from "../../components/keyboard_hint.tsx";
import { StatusBanner } from "../../components/status_banner.tsx";
import { DroppedSuggestions } from "../ai_redlines/dropped_suggestions.tsx";
import { RedlineComposer } from "../ai_redlines/redline_composer.tsx";
import { ApplyBar } from "./apply_bar.tsx";
import { SuggestionStatus, type ReviewSuggestion } from "./document_segments.ts";
import { SuggestionCard } from "./suggestion_card.tsx";
import styles from "./changes_panel.module.css";

const NETWORK_MESSAGE = "Can't reach the Redline server. Check that it's running.";
const AI_NOT_CONFIGURED_MESSAGE =
  "AI suggestions aren't set up. Add ANTHROPIC_API_KEY to .env and restart the server.";
const MODEL_FAILURE_MESSAGE = "Claude couldn't finish this review. Try again.";
const STALE_REVIEW_MESSAGE =
  "This contract changed since the review. Run the review again to get fresh suggestions.";
const REVIEWING_MESSAGE = "Reviewing the agreement. This usually takes under 15 seconds.";
const NETWORK_STATUS = 0;

/**
 * The review column: the composer, the suggestions, and the apply bar.
 * @param contractOpen - Whether a contract is open.
 * @param suggestions - The open suggestions, or none.
 * @param dropped - Suggestions that could not be placed.
 * @param activeSuggestionId - The suggestion the keyboard is on.
 * @param instruction - The instruction in the composer.
 * @param instructionMissing - Whether the last submit was empty.
 * @param reviewing - Whether a review is in flight.
 * @param suggestError - The last review failure, or null.
 * @param staleReview - Whether the contract changed after the review.
 * @param applyNote - Why the last apply did not run, or an empty string.
 * @param onInstructionChange - Stores the typed instruction.
 * @param onSubmitInstruction - Sends an instruction.
 * @param onSelectSuggestion - Makes a suggestion active.
 * @param onHoverSuggestion - Highlights the matching text.
 * @param onAccept - Accepts a suggestion.
 * @param onReject - Rejects a suggestion.
 * @param onUndo - Returns a suggestion to pending.
 * @param onAcceptAll - Accepts every pending suggestion.
 * @param onApply - Applies the accepted suggestions.
 * @param onDiscard - Closes the review.
 * @returns The column.
 * @throws Does not throw.
 */
export function ChangesPanel({
  contractOpen,
  suggestions,
  dropped,
  activeSuggestionId,
  instruction,
  instructionMissing,
  reviewing,
  suggestError,
  staleReview,
  applyNote,
  onInstructionChange,
  onSubmitInstruction,
  onSelectSuggestion,
  onHoverSuggestion,
  onAccept,
  onReject,
  onUndo,
  onAcceptAll,
  onApply,
  onDiscard,
}: {
  contractOpen: boolean;
  suggestions: ReviewSuggestion[] | null;
  dropped: DroppedSuggestionResponse[];
  activeSuggestionId: string | null;
  instruction: string;
  instructionMissing: boolean;
  reviewing: boolean;
  suggestError: unknown;
  staleReview: boolean;
  applyNote: string;
  onInstructionChange: (instruction: string) => void;
  onSubmitInstruction: (instruction: string) => void;
  onSelectSuggestion: (suggestionId: string) => void;
  onHoverSuggestion: (suggestionId: string | null) => void;
  onAccept: (suggestionId: string) => void;
  onReject: (suggestionId: string) => void;
  onUndo: (suggestionId: string) => void;
  onAcceptAll: () => void;
  onApply: () => void;
  onDiscard: () => void;
}): ReactNode {
  const acceptedCount =
    suggestions?.filter((suggestion) => suggestion.status === SuggestionStatus.Accepted).length ??
    0;
  const activePosition = activePositionLabel(suggestions, activeSuggestionId);
  return (
    <aside className={styles.panel}>
      {suggestions !== null && !reviewing ? (
        <header className={styles.header}>
          <h2 className={styles.heading}>Changes</h2>
          <p className={styles.progress}>{activePosition}</p>
        </header>
      ) : null}
      <div className={styles.body}>
        {reviewing ? <Reviewing /> : null}
        {!reviewing && suggestError !== null ? (
          <StatusBanner
            message={suggestErrorMessage(suggestError)}
            actionLabel={canRetry(suggestError) ? "Try again" : ""}
            onAction={() => onSubmitInstruction(instruction)}
          />
        ) : null}
        {!reviewing && staleReview ? (
          <StatusBanner
            message={STALE_REVIEW_MESSAGE}
            actionLabel="Run again"
            onAction={() => onSubmitInstruction(instruction)}
          />
        ) : null}
        {!reviewing && suggestions !== null ? (
          <>
            <div className={styles.cards}>
              {suggestions.map((suggestion) => (
                <SuggestionCard
                  key={suggestion.suggestionId}
                  suggestion={suggestion}
                  active={suggestion.suggestionId === activeSuggestionId}
                  onSelect={() => onSelectSuggestion(suggestion.suggestionId)}
                  onHover={onHoverSuggestion}
                  onAccept={() => onAccept(suggestion.suggestionId)}
                  onReject={() => onReject(suggestion.suggestionId)}
                  onUndo={() => onUndo(suggestion.suggestionId)}
                />
              ))}
            </div>
            <DroppedSuggestions dropped={dropped} />
          </>
        ) : null}
        {!reviewing && suggestions === null && suggestError === null && contractOpen ? (
          <RedlineComposer
            instruction={instruction}
            instructionMissing={instructionMissing}
            onInstructionChange={onInstructionChange}
            onSubmit={onSubmitInstruction}
          />
        ) : null}
        {!reviewing && suggestions === null && suggestError === null && !contractOpen ? (
          <p className={styles.closedNote}>Open a contract to ask Claude for redlines.</p>
        ) : null}
      </div>
      {suggestions !== null && !reviewing ? (
        <ApplyBar
          acceptedCount={acceptedCount}
          note={applyNote}
          onApply={onApply}
          onAcceptAll={onAcceptAll}
          onDiscard={onDiscard}
        />
      ) : null}
      <footer className={styles.footer}>
        <span className={styles.hint}>
          <KeyboardHint keys="J" /> <KeyboardHint keys="K" /> to move
        </span>
        <span className={styles.hint}>
          <KeyboardHint keys="/" /> to search
        </span>
      </footer>
    </aside>
  );
}

/**
 * The waiting state while Claude reads the contract.
 * @returns The skeleton and the status.
 * @throws Does not throw.
 */
function Reviewing(): ReactNode {
  return (
    <div className={styles.loading} aria-live="polite">
      <div className={styles.line} />
      <div className={`${styles.line} ${styles.short}`} />
      <div className={styles.line} />
      <p className={styles.loadingNote}>{REVIEWING_MESSAGE}</p>
    </div>
  );
}

/**
 * Say where the active suggestion sits in the list.
 * @param suggestions - The open suggestions.
 * @param activeSuggestionId - The active one.
 * @returns The progress label.
 * @throws Does not throw.
 */
function activePositionLabel(
  suggestions: ReviewSuggestion[] | null,
  activeSuggestionId: string | null,
): string {
  if (suggestions === null || suggestions.length === 0) {
    return "0 of 0";
  }
  const index = suggestions.findIndex(
    (suggestion) => suggestion.suggestionId === activeSuggestionId,
  );
  const position = index === -1 ? 1 : index + 1;
  return `${position} of ${suggestions.length}`;
}

/**
 * Choose the message for a failed review.
 * @param error - The failure.
 * @returns The message and its next step.
 * @throws Does not throw.
 */
function suggestErrorMessage(error: unknown): string {
  if (!(error instanceof ApiError) || error.status === NETWORK_STATUS) {
    return NETWORK_MESSAGE;
  }
  if (error.errorType === ApiErrorType.AiNotConfigured) {
    return AI_NOT_CONFIGURED_MESSAGE;
  }
  if (
    error.errorType === ApiErrorType.ModelUnavailable ||
    error.errorType === ApiErrorType.ModelResponseInvalid
  ) {
    return MODEL_FAILURE_MESSAGE;
  }
  return NETWORK_MESSAGE;
}

/**
 * Return whether the failure is worth trying again.
 * @param error - The failure.
 * @returns Whether to show Try again.
 * @throws Does not throw.
 */
function canRetry(error: unknown): boolean {
  return (
    error instanceof ApiError &&
    (error.errorType === ApiErrorType.ModelUnavailable ||
      error.errorType === ApiErrorType.ModelResponseInvalid)
  );
}
