import type { components } from "./schema.ts";

export type DocumentResponse = components["schemas"]["DocumentResponse"];
export type DocumentSummaryResponse = components["schemas"]["DocumentSummaryResponse"];
export type DocumentListResponse = components["schemas"]["DocumentListResponse"];
export type AiRedlineResponse = components["schemas"]["AiRedlineResponse"];
export type SuggestionResponse = components["schemas"]["SuggestionResponse"];
export type DroppedSuggestionResponse = components["schemas"]["DroppedSuggestionResponse"];
export type DroppedSuggestionReason = components["schemas"]["DroppedSuggestionReason"];
export type ApplyChangesRequest = components["schemas"]["ApplyChangesRequest"];
export type ApplyChangesResponse = components["schemas"]["ApplyChangesResponse"];
export type ChangeRequest = components["schemas"]["ChangeRequest"];
export type SearchResponse = components["schemas"]["SearchResponse"];
export type SearchHitResponse = components["schemas"]["SearchHitResponse"];
export type SnippetResponse = components["schemas"]["SnippetResponse"];
export type TextSpanResponse = components["schemas"]["TextSpanResponse"];

export const ApiErrorType = {
  ValidationError: "validation_error",
  AiNotConfigured: "ai_not_configured",
  ModelUnavailable: "model_unavailable",
  ModelResponseInvalid: "model_response_invalid",
  PreconditionFailed: "precondition_failed",
  InternalError: "internal_error",
} as const;
export type ApiErrorType = (typeof ApiErrorType)[keyof typeof ApiErrorType];
