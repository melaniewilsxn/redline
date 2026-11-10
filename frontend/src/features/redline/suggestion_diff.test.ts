import { describe, expect, it } from "vitest";

import { SuggestionPartKind, buildSuggestionParts } from "./suggestion_diff.ts";

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

  it("joins unchanged parts back to the original and added parts to the replacement", () => {
    const originalText = "The Customer shall indemnify the Company.";
    const replacement = "The Customer will defend the Company.";

    const parts = buildSuggestionParts(originalText, replacement);

    const originalParts = parts
      .filter((part) => part.kind !== SuggestionPartKind.Added)
      .map((part) => part.text)
      .join("");
    const replacementParts = parts
      .filter((part) => part.kind !== SuggestionPartKind.Removed)
      .map((part) => part.text)
      .join("");
    expect(originalParts).toBe(originalText);
    expect(replacementParts).toBe(replacement);
  });
});
