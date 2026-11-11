import { describe, expect, it } from "vitest";

import { findTextMatches } from "./find_in_text.ts";

describe("find in text", () => {
  it("finds every case-insensitive occurrence", () => {
    const page = findTextMatches("Customer and customer", "CUSTOMER", 10);

    expect(page.matches).toEqual([
      { start: 0, end: 8 },
      { start: 13, end: 21 },
    ]);
    expect(page.capped).toBe(false);
  });

  it("matches partial words literally", () => {
    const page = findTextMatches("Master Services", "Mas", 10);

    expect(page.matches).toEqual([{ start: 0, end: 3 }]);
  });

  it("matches a multi-word phrase literally, not as separate words", () => {
    const page = findTextMatches("Customer shall pay. The Customer waits.", "Customer shall", 10);

    expect(page.matches).toEqual([{ start: 0, end: 14 }]);
  });

  it("does not return overlapping matches", () => {
    const page = findTextMatches("aaaa", "aa", 10);

    expect(page.matches).toEqual([
      { start: 0, end: 2 },
      { start: 2, end: 4 },
    ]);
  });

  it("caps the matches and reports it", () => {
    const page = findTextMatches("cat cat cat", "cat", 2);

    expect(page.matches).toEqual([
      { start: 0, end: 3 },
      { start: 4, end: 7 },
    ]);
    expect(page.capped).toBe(true);
  });

  it("returns no matches for a blank query", () => {
    expect(findTextMatches("Customer shall", "   ", 10)).toEqual({ matches: [], capped: false });
  });
});
