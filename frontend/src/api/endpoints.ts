import { requestJson, type ApiResponse } from "./client.ts";
import type {
  AiRedlineResponse,
  ApplyChangesResponse,
  ChangeRequest,
  DocumentListResponse,
  DocumentResponse,
  SearchMatchMode,
  SearchResponse,
} from "./types.ts";

const DOCUMENT_LIST_LIMIT = 100;
export const REVIEWER_NAME = "Reviewer";

/**
 * List the documents, up to one page of 100.
 * @returns The page and its ETag, which this read does not use.
 * @throws {ApiError} When the list cannot be loaded.
 */
export function listDocuments(): Promise<ApiResponse<DocumentListResponse>> {
  return requestJson<DocumentListResponse>(`/documents?limit=${DOCUMENT_LIST_LIMIT}`, {});
}

/**
 * Store a new contract.
 * @param title - The contract title.
 * @param text - The contract text.
 * @returns The new contract and its ETag.
 * @throws {ApiError} When the contract cannot be stored.
 */
export function createDocument(
  title: string,
  text: string,
): Promise<ApiResponse<DocumentResponse>> {
  return requestJson<DocumentResponse>("/documents", {
    method: "POST",
    body: JSON.stringify({ title, text, author: REVIEWER_NAME }),
  });
}

/**
 * Load one document.
 * @param documentId - The document to open.
 * @returns The document and the ETag of its current version.
 * @throws {ApiError} When the document is missing or the server cannot be reached.
 */
export function getDocument(documentId: string): Promise<ApiResponse<DocumentResponse>> {
  return requestJson<DocumentResponse>(`/documents/${documentId}`, {});
}

/**
 * Apply accepted suggestions to one version of a document.
 * @param documentId - The document to change.
 * @param etag - The ETag the suggestions were computed against, quotes included.
 * @param changes - The range changes to apply.
 * @param author - The name stored with the new version.
 * @returns The updated document.
 * @throws {ApiError} When the version is stale or the changes are rejected.
 */
export function applyChanges(
  documentId: string,
  etag: string,
  changes: ChangeRequest[],
  author: string,
): Promise<ApiResponse<ApplyChangesResponse>> {
  return requestJson<ApplyChangesResponse>(`/documents/${documentId}`, {
    method: "PATCH",
    headers: { "If-Match": etag },
    body: JSON.stringify({ author, changes }),
  });
}

/**
 * Search across documents.
 * @param query - The words or quoted phrase.
 * @param documentIds - The documents to search, or none to search all of them.
 * @param limit - How many documents to return.
 * @param mode - Exact words, or a prefix on the last word.
 * @returns The matching documents.
 * @throws {ApiError} When the query is empty or the server cannot be reached.
 */
export function searchDocuments(
  query: string,
  documentIds: string[],
  limit: number,
  mode: SearchMatchMode,
): Promise<ApiResponse<SearchResponse>> {
  const parameters = new URLSearchParams({ q: query, limit: String(limit), mode });
  for (const documentId of documentIds) {
    parameters.append("document_ids", documentId);
  }
  return requestJson<SearchResponse>(`/search?${parameters.toString()}`, {});
}

/**
 * Search inside one document.
 * @param documentId - The document to search.
 * @param query - The words or quoted phrase.
 * @param limit - How many hits to return.
 * @returns The match, with up to three snippets.
 * @throws {ApiError} When the query is empty or the document is missing.
 */
export function searchDocument(
  documentId: string,
  query: string,
  limit: number,
): Promise<ApiResponse<SearchResponse>> {
  const parameters = new URLSearchParams({ q: query, limit: String(limit) });
  return requestJson<SearchResponse>(
    `/documents/${documentId}/search?${parameters.toString()}`,
    {},
  );
}

/**
 * Ask for redline suggestions.
 * @param documentId - The document to review.
 * @param instruction - What the reviewer wants changed.
 * @returns The anchored and dropped suggestions, and the ETag they belong to.
 * @throws {ApiError} When the model is unavailable or the document is missing.
 */
export function suggestRedlines(
  documentId: string,
  instruction: string,
): Promise<ApiResponse<AiRedlineResponse>> {
  return requestJson<AiRedlineResponse>(`/documents/${documentId}/ai-redlines`, {
    method: "POST",
    body: JSON.stringify({ instruction }),
  });
}
