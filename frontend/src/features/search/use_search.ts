import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { searchDocument, searchDocuments } from "../../api/endpoints.ts";
import type { ApiResponse } from "../../api/client.ts";
import type { SearchResponse } from "../../api/types.ts";

const SEARCH_DEBOUNCE_MS = 250;
const MINIMUM_SEARCH_CHARACTERS = 2;
const SEARCH_PAGE_LIMIT = 20;

/**
 * Search every contract once the query has settled.
 * @param query - The text in the search field.
 * @returns The settled query and the search.
 * @throws Does not throw.
 */
export function useCrossDocumentSearch(query: string): {
  settledQuery: string;
  searching: boolean;
  search: UseQueryResult<ApiResponse<SearchResponse>>;
} {
  const settledQuery = useSettledQuery(query);
  const searching = settledQuery.length >= MINIMUM_SEARCH_CHARACTERS;
  const search = useQuery({
    queryKey: ["search", settledQuery],
    queryFn: () => searchDocuments(settledQuery, [], SEARCH_PAGE_LIMIT),
    enabled: searching,
  });
  return { settledQuery, searching, search };
}

/**
 * Search inside one contract once the query has settled.
 * @param documentId - The open contract.
 * @param query - The text in the in-document field.
 * @returns The settled query and the search.
 * @throws Does not throw.
 */
export function useDocumentSearch(
  documentId: string,
  query: string,
): {
  settledQuery: string;
  searching: boolean;
  search: UseQueryResult<ApiResponse<SearchResponse>>;
} {
  const settledQuery = useSettledQuery(query);
  const searching = settledQuery.length >= MINIMUM_SEARCH_CHARACTERS;
  const search = useQuery({
    queryKey: ["search", documentId, settledQuery],
    queryFn: () => searchDocument(documentId, settledQuery, SEARCH_PAGE_LIMIT),
    enabled: searching,
  });
  return { settledQuery, searching, search };
}

/**
 * Wait briefly before treating the query as ready.
 * @param query - The text the user is typing.
 * @returns The query after the pause.
 * @throws Does not throw.
 */
function useSettledQuery(query: string): string {
  const trimmed = query.trim();
  const [settledQuery, setSettledQuery] = useState(trimmed);
  if (trimmed === "" && settledQuery !== "") {
    setSettledQuery("");
  }
  useEffect(() => {
    if (trimmed === "") {
      return;
    }
    const timer = window.setTimeout(() => setSettledQuery(trimmed), SEARCH_DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [trimmed]);
  return trimmed === "" ? "" : settledQuery;
}
