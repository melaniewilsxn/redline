import { diffWordsWithSpace, type Change } from "diff";

export const SuggestionPartKind = {
  Unchanged: "unchanged",
  Removed: "removed",
  Added: "added",
} as const;
export type SuggestionPartKind = (typeof SuggestionPartKind)[keyof typeof SuggestionPartKind];

export interface SuggestionPart {
  kind: SuggestionPartKind;
  text: string;
}

/**
 * Compare the original words with the replacement.
 * @param originalText - The words the suggestion replaces.
 * @param replacement - The words the suggestion would insert.
 * @returns The unchanged, removed, and added parts, in order.
 * @throws Does not throw.
 */
export function buildSuggestionParts(originalText: string, replacement: string): SuggestionPart[] {
  const parts: SuggestionPart[] = [];
  for (const change of diffWordsWithSpace(originalText, replacement)) {
    if (change.value === "") {
      continue;
    }
    parts.push({ kind: getPartKind(change), text: change.value });
  }
  return parts;
}

/**
 * Name a diff piece as unchanged, removed, or added.
 * @param change - One piece from the word diff.
 * @returns The part kind.
 * @throws Does not throw.
 */
function getPartKind(change: Change): SuggestionPartKind {
  if (change.added === true) {
    return SuggestionPartKind.Added;
  }
  if (change.removed === true) {
    return SuggestionPartKind.Removed;
  }
  return SuggestionPartKind.Unchanged;
}
