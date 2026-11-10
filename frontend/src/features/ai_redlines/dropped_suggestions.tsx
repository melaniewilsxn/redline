import { useState, type ReactNode } from "react";

import type { DroppedSuggestionReason, DroppedSuggestionResponse } from "../../api/types.ts";
import styles from "./dropped_suggestions.module.css";

/**
 * Suggestions that could not be placed, collapsed until the reviewer asks.
 * @param dropped - The suggestions the document could not hold.
 * @returns The row, or nothing when every suggestion was placed.
 * @throws Does not throw.
 */
export function DroppedSuggestions({
  dropped,
}: {
  dropped: DroppedSuggestionResponse[];
}): ReactNode {
  const [expanded, setExpanded] = useState(false);
  if (dropped.length === 0) {
    return null;
  }
  return (
    <div>
      <button type="button" className={styles.row} onClick={() => setExpanded((open) => !open)}>
        {droppedLabel(dropped.length)}
      </button>
      {expanded ? (
        <ul className={styles.list}>
          {dropped.map((suggestion) => (
            <li key={suggestion.suggestion_id} className={styles.item}>
              <span>{suggestion.text}</span>
              <p className={styles.reason}>{droppedReasonLabel(suggestion.reason)}</p>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

/**
 * Name how many suggestions could not be placed.
 * @param count - How many were dropped.
 * @returns The row label.
 * @throws Does not throw.
 */
function droppedLabel(count: number): string {
  if (count === 1) {
    return "1 suggestion couldn't be placed";
  }
  return `${count} suggestions couldn't be placed`;
}

/**
 * Say why a suggestion was not placed.
 * @param reason - The reason from the API.
 * @returns The sentence shown to the reviewer.
 * @throws Does not throw.
 */
function droppedReasonLabel(reason: DroppedSuggestionReason): string {
  switch (reason) {
    case "empty_target":
      return "The suggestion didn't point at any text.";
    case "no_change":
      return "The suggestion didn't change the text.";
    case "target_not_found":
      return "That text isn't in this version.";
    case "ambiguous_target":
      return "That text appears more than once, so it wasn't placed.";
    case "overlaps_earlier_suggestion":
      return "This overlaps an earlier suggestion.";
    default:
      return "This suggestion couldn't be placed.";
  }
}
