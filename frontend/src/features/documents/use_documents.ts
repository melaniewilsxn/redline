import { skipToken, useQuery, type UseQueryResult } from "@tanstack/react-query";

import { getDocument, listDocuments } from "../../api/endpoints.ts";
import type { ApiResponse } from "../../api/client.ts";
import type { DocumentListResponse, DocumentResponse } from "../../api/types.ts";

/**
 * Load the contract list.
 * @returns The list query.
 * @throws Does not throw.
 */
export function useDocumentList(): UseQueryResult<ApiResponse<DocumentListResponse>> {
  return useQuery({
    queryKey: ["documents"],
    queryFn: listDocuments,
  });
}

/**
 * Load one contract.
 * @param documentId - The contract to open, or null when none is selected.
 * @returns The document query.
 * @throws Does not throw.
 */
export function useDocument(
  documentId: string | null,
): UseQueryResult<ApiResponse<DocumentResponse>> {
  return useQuery({
    queryKey: ["document", documentId],
    queryFn: documentId === null ? skipToken : () => getDocument(documentId),
  });
}
