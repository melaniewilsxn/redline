import { useMutation, type UseMutationResult } from "@tanstack/react-query";

import type { ApiResponse } from "../../api/client.ts";
import { suggestRedlines } from "../../api/endpoints.ts";
import type { AiRedlineResponse } from "../../api/types.ts";

export interface SuggestRedlinesRequest {
  documentId: string;
  instruction: string;
}

const MUTATION_RETRY_LIMIT = false;

/**
 * Ask for redlines. A failed request is not sent again on its own.
 * @returns The mutation.
 * @throws Does not throw.
 */
export function useSuggestRedlines(): UseMutationResult<
  ApiResponse<AiRedlineResponse>,
  unknown,
  SuggestRedlinesRequest
> {
  return useMutation({
    mutationFn: (request: SuggestRedlinesRequest) =>
      suggestRedlines(request.documentId, request.instruction),
    retry: MUTATION_RETRY_LIMIT,
  });
}
