import { describe, expect, it } from "vitest";

import { chooseShownTextHits, keepPreviousTextResults } from "./use_search.ts";

const PREVIOUS_HITS = ["customer"];

describe("previous text results", () => {
  it("keeps hits while the query extends the previous one", () => {
    expect(keepPreviousTextResults(PREVIOUS_HITS, "inde", "indem")).toEqual(PREVIOUS_HITS);
  });

  it("drops hits when the query does not extend the previous one", () => {
    expect(keepPreviousTextResults(PREVIOUS_HITS, "customer", "Mas")).toBeUndefined();
  });
});

describe("shown text hits", () => {
  it("keeps hits while the field still continues the settled query", () => {
    expect(chooseShownTextHits(PREVIOUS_HITS, "inde", "indem")).toEqual(PREVIOUS_HITS);
    expect(chooseShownTextHits(PREVIOUS_HITS, "inde", "inde")).toEqual(PREVIOUS_HITS);
  });

  it("drops hits when the field no longer continues the settled query", () => {
    expect(chooseShownTextHits(PREVIOUS_HITS, "Mas", "indemn")).toEqual([]);
    expect(chooseShownTextHits(PREVIOUS_HITS, "", "M")).toEqual([]);
  });
});
