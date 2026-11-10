import type { ChangeRequest, DroppedSuggestionResponse } from "../../api/types.ts";
import { SuggestionStatus, type ReviewSuggestion } from "./document_segments.ts";

export const MoveDirection = {
  Next: "next",
  Previous: "previous",
} as const;
export type MoveDirection = (typeof MoveDirection)[keyof typeof MoveDirection];

export const RangeTargetType = {
  Range: "range",
} as const;

export const ReviewActionType = {
  Loaded: "loaded",
  Moved: "moved",
  Selected: "selected",
  Accepted: "accepted",
  Rejected: "rejected",
  Undone: "undone",
  AcceptedAll: "acceptedAll",
  Cleared: "cleared",
} as const;

export interface SuggestionResponseFields {
  suggestion_id: string;
  start: number;
  end: number;
  original_text: string;
  replacement: string;
  rationale: string;
  title: string;
}

export interface AiRedlineFields {
  suggestions: SuggestionResponseFields[];
  dropped: DroppedSuggestionResponse[];
}

export interface ReviewState {
  documentId: string;
  etag: string;
  suggestions: ReviewSuggestion[];
  dropped: DroppedSuggestionResponse[];
  activeSuggestionId: string | null;
}

export type ReviewAction =
  | {
      type: typeof ReviewActionType.Loaded;
      documentId: string;
      etag: string;
      response: AiRedlineFields;
    }
  | { type: typeof ReviewActionType.Moved; direction: MoveDirection }
  | { type: typeof ReviewActionType.Selected; suggestionId: string }
  | { type: typeof ReviewActionType.Accepted; suggestionId: string }
  | { type: typeof ReviewActionType.Rejected; suggestionId: string }
  | { type: typeof ReviewActionType.Undone; suggestionId: string }
  | { type: typeof ReviewActionType.AcceptedAll }
  | { type: typeof ReviewActionType.Cleared };

/**
 * Map one API suggestion onto a pending review suggestion.
 * @param suggestion - The suggestion returned by the API.
 * @returns The suggestion the review can accept or reject.
 * @throws Does not throw.
 */
export function toReviewSuggestion(suggestion: SuggestionResponseFields): ReviewSuggestion {
  return {
    suggestionId: suggestion.suggestion_id,
    start: suggestion.start,
    end: suggestion.end,
    originalText: suggestion.original_text,
    replacement: suggestion.replacement,
    rationale: suggestion.rationale,
    title: suggestion.title,
    status: SuggestionStatus.Pending,
  };
}

/**
 * Apply one review action.
 * @param state - The current review, or null when none is open.
 * @param action - The action to apply.
 * @returns The next review, or null when it was cleared.
 * @throws Does not throw.
 */
export function reduceReview(state: ReviewState | null, action: ReviewAction): ReviewState | null {
  switch (action.type) {
    case ReviewActionType.Loaded:
      return loadReview(action.documentId, action.etag, action.response);
    case ReviewActionType.Cleared:
      return null;
    case ReviewActionType.Moved:
      return state === null ? null : moveReview(state, action.direction);
    case ReviewActionType.Selected:
      return state === null ? null : selectSuggestion(state, action.suggestionId);
    case ReviewActionType.Accepted:
      return state === null
        ? null
        : decideSuggestion(state, action.suggestionId, SuggestionStatus.Accepted);
    case ReviewActionType.Rejected:
      return state === null
        ? null
        : decideSuggestion(state, action.suggestionId, SuggestionStatus.Rejected);
    case ReviewActionType.Undone:
      return state === null ? null : undoSuggestion(state, action.suggestionId);
    case ReviewActionType.AcceptedAll:
      return state === null ? null : acceptPendingSuggestions(state);
    default:
      return state;
  }
}

/**
 * Build the range changes for the suggestions the reviewer accepted.
 * @param state - The open review.
 * @returns Range targets in suggestion order.
 * @throws Does not throw.
 */
export function getAcceptedChanges(state: ReviewState): ChangeRequest[] {
  return state.suggestions
    .filter((suggestion) => suggestion.status === SuggestionStatus.Accepted)
    .map((suggestion) => ({
      target: {
        type: RangeTargetType.Range,
        start: suggestion.start,
        end: suggestion.end,
      },
      replacement: suggestion.replacement,
    }));
}

/**
 * Open a review with every suggestion pending and the first one active.
 * @param documentId - The document the suggestions belong to.
 * @param etag - The version the suggestions were computed against.
 * @param response - The anchored and dropped suggestions.
 * @returns The new review.
 * @throws Does not throw.
 */
function loadReview(documentId: string, etag: string, response: AiRedlineFields): ReviewState {
  const suggestions = response.suggestions.map(toReviewSuggestion);
  const first = suggestions[0];
  return {
    documentId,
    etag,
    suggestions,
    dropped: response.dropped,
    activeSuggestionId: first === undefined ? null : first.suggestionId,
  };
}

/**
 * Move the active suggestion, wrapping at either end.
 * @param state - The open review.
 * @param direction - Which way to move.
 * @returns The review with a new active suggestion.
 * @throws Does not throw.
 */
function moveReview(state: ReviewState, direction: MoveDirection): ReviewState {
  if (state.suggestions.length === 0) {
    return state;
  }
  const currentIndex = state.suggestions.findIndex(
    (suggestion) => suggestion.suggestionId === state.activeSuggestionId,
  );
  const startIndex = currentIndex === -1 ? 0 : currentIndex;
  const delta = direction === MoveDirection.Next ? 1 : -1;
  const nextIndex = (startIndex + delta + state.suggestions.length) % state.suggestions.length;
  const next = state.suggestions[nextIndex];
  if (next === undefined) {
    return state;
  }
  return { ...state, activeSuggestionId: next.suggestionId };
}

/**
 * Make one suggestion active.
 * @param state - The open review.
 * @param suggestionId - The suggestion the reviewer chose.
 * @returns The review, unchanged when the id is unknown.
 * @throws Does not throw.
 */
function selectSuggestion(state: ReviewState, suggestionId: string): ReviewState {
  const found = state.suggestions.some((suggestion) => suggestion.suggestionId === suggestionId);
  if (!found) {
    return state;
  }
  return { ...state, activeSuggestionId: suggestionId };
}

/**
 * Accept or reject one suggestion and move to the next one that is still pending.
 * @param state - The open review.
 * @param suggestionId - The suggestion being decided.
 * @param status - The decision.
 * @returns The review after the decision.
 * @throws Does not throw.
 */
function decideSuggestion(
  state: ReviewState,
  suggestionId: string,
  status: typeof SuggestionStatus.Accepted | typeof SuggestionStatus.Rejected,
): ReviewState {
  const index = state.suggestions.findIndex(
    (suggestion) => suggestion.suggestionId === suggestionId,
  );
  if (index === -1) {
    return state;
  }
  const suggestions = state.suggestions.map((suggestion) =>
    suggestion.suggestionId === suggestionId ? { ...suggestion, status } : suggestion,
  );
  const nextPendingId = findNextPendingId(suggestions, index);
  return {
    ...state,
    suggestions,
    activeSuggestionId: nextPendingId ?? suggestionId,
  };
}

/**
 * Return a decided suggestion to pending and make it active.
 * @param state - The open review.
 * @param suggestionId - The suggestion to undo.
 * @returns The review with that suggestion pending.
 * @throws Does not throw.
 */
function undoSuggestion(state: ReviewState, suggestionId: string): ReviewState {
  const found = state.suggestions.some((suggestion) => suggestion.suggestionId === suggestionId);
  if (!found) {
    return state;
  }
  return {
    ...state,
    suggestions: state.suggestions.map((suggestion) =>
      suggestion.suggestionId === suggestionId
        ? { ...suggestion, status: SuggestionStatus.Pending }
        : suggestion,
    ),
    activeSuggestionId: suggestionId,
  };
}

/**
 * Accept every suggestion that is still pending.
 * @param state - The open review.
 * @returns The review with no pending suggestions.
 * @throws Does not throw.
 */
function acceptPendingSuggestions(state: ReviewState): ReviewState {
  return {
    ...state,
    suggestions: state.suggestions.map((suggestion) =>
      suggestion.status === SuggestionStatus.Pending
        ? { ...suggestion, status: SuggestionStatus.Accepted }
        : suggestion,
    ),
  };
}

/**
 * Find the next pending suggestion after an index, wrapping around the list.
 * @param suggestions - The suggestions after the decision.
 * @param fromIndex - The suggestion that was just decided.
 * @returns The next pending id, or null when none remain.
 * @throws Does not throw.
 */
function findNextPendingId(suggestions: ReviewSuggestion[], fromIndex: number): string | null {
  for (let offset = 1; offset <= suggestions.length; offset += 1) {
    const suggestion = suggestions[(fromIndex + offset) % suggestions.length];
    if (suggestion !== undefined && suggestion.status === SuggestionStatus.Pending) {
      return suggestion.suggestionId;
    }
  }
  return null;
}
