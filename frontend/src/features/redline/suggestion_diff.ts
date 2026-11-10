import { diffWordsWithSpace, type Change } from "diff";

const SHORT_UNCHANGED_WORD_COUNT = 2;

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
 * @returns Phrase-level unchanged, removed, and added parts, in order.
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
  return groupChangePhrases(parts);
}

/**
 * Return the space drawn between a deletion and the insertion after it.
 * @param removedText - The deleted phrase.
 * @param addedText - The inserted phrase.
 * @returns A space when the two phrases would otherwise touch, or an empty string.
 * @throws Does not throw.
 */
export function getRenderedSeparator(removedText: string, addedText: string): string {
  if (/\s$/u.test(removedText) || /^\s/u.test(addedText)) {
    return "";
  }
  return " ";
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

/**
 * Fold a word diff into phrase-level changes.
 * @param parts - The word diff, with empty pieces already removed.
 * @returns Unchanged text, then each change as its removed phrase followed by its added phrase.
 * @throws Does not throw.
 */
function groupChangePhrases(parts: SuggestionPart[]): SuggestionPart[] {
  const phrases: SuggestionPart[] = [];
  let index = 0;
  while (index < parts.length) {
    const part = parts[index];
    if (part.kind === SuggestionPartKind.Unchanged && !isAbsorbedUnchanged(parts, index)) {
      phrases.push(part);
      index += 1;
      continue;
    }
    const removedPieces: string[] = [];
    const addedPieces: string[] = [];
    while (index < parts.length) {
      const current = parts[index];
      if (current.kind === SuggestionPartKind.Unchanged && !isAbsorbedUnchanged(parts, index)) {
        break;
      }
      if (current.kind !== SuggestionPartKind.Added) {
        removedPieces.push(current.text);
      }
      if (current.kind !== SuggestionPartKind.Removed) {
        addedPieces.push(current.text);
      }
      index += 1;
    }
    const removedText = removedPieces.join("");
    const addedText = addedPieces.join("");
    if (removedText !== "") {
      phrases.push({ kind: SuggestionPartKind.Removed, text: removedText });
    }
    if (addedText !== "") {
      phrases.push({ kind: SuggestionPartKind.Added, text: addedText });
    }
  }
  return phrases;
}

/**
 * Report whether this unchanged piece belongs inside the change around it.
 * @param parts - The word diff.
 * @param index - The unchanged piece.
 * @returns True when the piece is short and both neighbors are changes.
 * @throws Does not throw.
 */
function isAbsorbedUnchanged(parts: SuggestionPart[], index: number): boolean {
  if (index === 0 || index === parts.length - 1) {
    return false;
  }
  const part = parts[index];
  const previous = parts[index - 1];
  const next = parts[index + 1];
  if (part.kind !== SuggestionPartKind.Unchanged) {
    return false;
  }
  if (
    previous.kind === SuggestionPartKind.Unchanged ||
    next.kind === SuggestionPartKind.Unchanged
  ) {
    return false;
  }
  return isShortUnchanged(part.text);
}

/**
 * Report whether an unchanged piece is only a couple of words, or no words at all.
 * @param text - The unchanged piece.
 * @returns True for whitespace, punctuation, or at most two words.
 * @throws Does not throw.
 */
function isShortUnchanged(text: string): boolean {
  if (!hasWord(text)) {
    return true;
  }
  return countWords(text) <= SHORT_UNCHANGED_WORD_COUNT;
}

/**
 * Report whether the text contains a word.
 * @param text - The piece to inspect.
 * @returns True when a letter or number is present.
 * @throws Does not throw.
 */
function hasWord(text: string): boolean {
  return /\p{L}|\p{N}/u.test(text);
}

/**
 * Count the words in a piece.
 * @param text - The piece to inspect.
 * @returns How many words it contains.
 * @throws Does not throw.
 */
function countWords(text: string): number {
  return text.split(/\s+/u).filter((word) => hasWord(word)).length;
}
