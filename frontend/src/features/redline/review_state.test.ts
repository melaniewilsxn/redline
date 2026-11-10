import { describe, expect, it } from "vitest";

import { SuggestionStatus } from "./document_segments.ts";
import {
  MoveDirection,
  RangeTargetType,
  ReviewActionType,
  getAcceptedChanges,
  reduceReview,
  type AiRedlineFields,
  type ReviewState,
} from "./review_state.ts";

const DOCUMENT_ID = "document-1";
const ETAG = '"document-1-1"';

/**
 * Build a response with two suggestions.
 * @returns The API shape the review loads.
 * @throws Does not throw.
 */
function buildResponse(): AiRedlineFields {
  return {
    suggestions: [
      {
        suggestion_id: "s1",
        start: 0,
        end: 5,
        original_text: "Hello",
        replacement: "Hi",
        rationale: "Prefer the shorter greeting.",
      },
      {
        suggestion_id: "s2",
        start: 6,
        end: 11,
        original_text: "world",
        replacement: "there",
        rationale: "Use the other word.",
      },
    ],
    dropped: [],
  };
}

/**
 * Load the sample review.
 * @returns A review whose suggestions are pending.
 * @throws {Error} When the review does not load.
 */
function loadReview(): ReviewState {
  const state = reduceReview(null, {
    type: ReviewActionType.Loaded,
    documentId: DOCUMENT_ID,
    etag: ETAG,
    response: buildResponse(),
  });
  if (state === null) {
    throw new Error("review did not load");
  }
  return state;
}

describe("review state", () => {
  it("loaded makes every suggestion pending and the first active", () => {
    const state = loadReview();

    expect(state.activeSuggestionId).toBe("s1");
    expect(state.etag).toBe(ETAG);
    expect(state.suggestions.map((suggestion) => suggestion.status)).toEqual([
      SuggestionStatus.Pending,
      SuggestionStatus.Pending,
    ]);
    expect(state.suggestions[0]?.originalText).toBe("Hello");
  });

  it("moved next wraps from last to first", () => {
    const loaded = loadReview();
    const onLast = reduceReview(loaded, {
      type: ReviewActionType.Selected,
      suggestionId: "s2",
    });

    const state = reduceReview(onLast, {
      type: ReviewActionType.Moved,
      direction: MoveDirection.Next,
    });

    expect(state?.activeSuggestionId).toBe("s1");
  });

  it("moved previous wraps from first to last", () => {
    const state = reduceReview(loadReview(), {
      type: ReviewActionType.Moved,
      direction: MoveDirection.Previous,
    });

    expect(state?.activeSuggestionId).toBe("s2");
  });

  it("moved next goes to the following suggestion when not at the end", () => {
    const state = reduceReview(loadReview(), {
      type: ReviewActionType.Moved,
      direction: MoveDirection.Next,
    });

    expect(state?.activeSuggestionId).toBe("s2");
  });

  it("accepted marks the active suggestion and moves to the next pending one", () => {
    const state = reduceReview(loadReview(), {
      type: ReviewActionType.Accepted,
      suggestionId: "s1",
    });

    expect(state?.suggestions[0]?.status).toBe(SuggestionStatus.Accepted);
    expect(state?.suggestions[1]?.status).toBe(SuggestionStatus.Pending);
    expect(state?.activeSuggestionId).toBe("s2");
  });

  it("rejected marks the active suggestion and moves to the next pending one", () => {
    const state = reduceReview(loadReview(), {
      type: ReviewActionType.Rejected,
      suggestionId: "s1",
    });

    expect(state?.suggestions[0]?.status).toBe(SuggestionStatus.Rejected);
    expect(state?.activeSuggestionId).toBe("s2");
  });

  it("accepted with no pending suggestions left keeps the active one", () => {
    const loaded = loadReview();
    const firstAccepted = reduceReview(loaded, {
      type: ReviewActionType.Accepted,
      suggestionId: "s1",
    });

    const state = reduceReview(firstAccepted, {
      type: ReviewActionType.Accepted,
      suggestionId: "s2",
    });

    expect(
      state?.suggestions.every((suggestion) => suggestion.status === SuggestionStatus.Accepted),
    ).toBe(true);
    expect(state?.activeSuggestionId).toBe("s2");
  });

  it("undone returns a decided suggestion to pending", () => {
    const accepted = reduceReview(loadReview(), {
      type: ReviewActionType.Accepted,
      suggestionId: "s1",
    });

    const state = reduceReview(accepted, { type: ReviewActionType.Undone, suggestionId: "s1" });

    expect(state?.suggestions[0]?.status).toBe(SuggestionStatus.Pending);
    expect(state?.activeSuggestionId).toBe("s1");
  });

  it("acceptedAll accepts only pending suggestions", () => {
    const rejected = reduceReview(loadReview(), {
      type: ReviewActionType.Rejected,
      suggestionId: "s1",
    });

    const state = reduceReview(rejected, { type: ReviewActionType.AcceptedAll });

    expect(state?.suggestions[0]?.status).toBe(SuggestionStatus.Rejected);
    expect(state?.suggestions[1]?.status).toBe(SuggestionStatus.Accepted);
  });

  it("getAcceptedChanges returns range targets for accepted suggestions only", () => {
    const state = reduceReview(loadReview(), {
      type: ReviewActionType.Accepted,
      suggestionId: "s2",
    });
    if (state === null) {
      throw new Error("review did not accept");
    }

    const changes = getAcceptedChanges(state);

    expect(changes).toEqual([
      {
        target: { type: RangeTargetType.Range, start: 6, end: 11 },
        replacement: "there",
      },
    ]);
  });

  it("selected makes that suggestion active", () => {
    const state = reduceReview(loadReview(), {
      type: ReviewActionType.Selected,
      suggestionId: "s2",
    });

    expect(state?.activeSuggestionId).toBe("s2");
    expect(state?.suggestions[1]?.status).toBe(SuggestionStatus.Pending);
  });

  it("cleared empties the review", () => {
    const state = reduceReview(loadReview(), { type: ReviewActionType.Cleared });

    expect(state).toBeNull();
  });
});
