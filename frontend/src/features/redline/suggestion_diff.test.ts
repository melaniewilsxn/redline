import { describe, expect, it } from "vitest";

import {
  SuggestionPartKind,
  buildSuggestionParts,
  getRenderedSeparator,
} from "./suggestion_diff.ts";

describe("suggestion diff", () => {
  it("keeps unchanged words between a removed and an added word", () => {
    const parts = buildSuggestionParts("the cat sat", "the dog sat");

    expect(parts.map((part) => part.kind)).toEqual([
      SuggestionPartKind.Unchanged,
      SuggestionPartKind.Removed,
      SuggestionPartKind.Added,
      SuggestionPartKind.Unchanged,
    ]);
    expect(parts.map((part) => part.text)).toEqual(["the ", "cat", "dog", " sat"]);
  });

  it("returns one added part for a pure insertion", () => {
    const parts = buildSuggestionParts("", "hello");

    expect(parts).toEqual([{ kind: SuggestionPartKind.Added, text: "hello" }]);
  });

  it("returns one removed part for a pure deletion", () => {
    const parts = buildSuggestionParts("hello", "");

    expect(parts).toEqual([{ kind: SuggestionPartKind.Removed, text: "hello" }]);
  });

  it("absorbs a short unchanged run between two changes", () => {
    const parts = buildSuggestionParts("the cat sat quietly", "the dog ran quietly");

    expect(parts.map((part) => part.text)).toEqual(["the ", "cat sat", "dog ran", " quietly"]);
  });

  it("keeps a long unchanged run between two changes", () => {
    const parts = buildSuggestionParts("one two three four five", "ONE two three four FIVE");

    expect(parts.map((part) => part.kind)).toEqual([
      SuggestionPartKind.Removed,
      SuggestionPartKind.Added,
      SuggestionPartKind.Unchanged,
      SuggestionPartKind.Removed,
      SuggestionPartKind.Added,
    ]);
    expect(parts.map((part) => part.text)).toEqual([
      "one",
      "ONE",
      " two three four ",
      "five",
      "FIVE",
    ]);
  });

  it("merges neighbouring changes into one removed and one added phrase", () => {
    const parts = buildSuggestionParts("cat or dog", "mouse and hound");

    expect(parts).toEqual([
      { kind: SuggestionPartKind.Removed, text: "cat or dog" },
      { kind: SuggestionPartKind.Added, text: "mouse and hound" },
    ]);
  });

  it("joins unchanged parts back to the original and added parts to the replacement", () => {
    const simpleOriginal = "The Customer shall indemnify the Company.";
    const simpleReplacement = "The Customer will defend the Company.";
    const heavyOriginal =
      "the Company's total liability is not capped by the fees paid and is not limited to a multiple of those fees. The Customer has asked for that allocation, and the price does not include a discount in exchange for a cap.";
    const heavyReplacement =
      "each party's total liability is capped at the fees paid or payable under this agreement in the 12 months before the claim arose.";

    expect(roundTrip(simpleOriginal, simpleReplacement)).toEqual({
      original: simpleOriginal,
      replacement: simpleReplacement,
    });
    expect(roundTrip(heavyOriginal, heavyReplacement)).toEqual({
      original: heavyOriginal,
      replacement: heavyReplacement,
    });
  });

  it("draws a space only when a deletion would touch the insertion", () => {
    expect(getRenderedSeparator("The", "Each")).toBe(" ");
    expect(getRenderedSeparator("The ", "Each")).toBe("");
    expect(getRenderedSeparator("The", " Each")).toBe("");
  });
});

/**
 * Join the parts back into the original and the replacement.
 * @param originalText - The words the suggestion replaces.
 * @param replacement - The words the suggestion would insert.
 * @returns Both reconstructions.
 * @throws Does not throw.
 */
function roundTrip(
  originalText: string,
  replacement: string,
): { original: string; replacement: string } {
  const parts = buildSuggestionParts(originalText, replacement);
  return {
    original: parts
      .filter((part) => part.kind !== SuggestionPartKind.Added)
      .map((part) => part.text)
      .join(""),
    replacement: parts
      .filter((part) => part.kind !== SuggestionPartKind.Removed)
      .map((part) => part.text)
      .join(""),
  };
}
