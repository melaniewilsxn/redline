import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { searchDocuments } from "../../api/endpoints.ts";
import type { ApiResponse } from "../../api/client.ts";
import { SearchMatchMode, type SearchHitResponse, type SearchResponse } from "../../api/types.ts";

const SEARCH_DEBOUNCE_MS = 150;
const MINIMUM_SEARCH_CHARACTERS = 2;
const SEARCH_PAGE_LIMIT = 20;

/**
 * Search every contract once the query has settled.
 * @param query - The text in the search field.
 * @returns The live query, the settled query, and the text hits still worth showing.
 * @throws Does not throw.
 */
export function useCrossDocumentSearch(query: string): {
  trimmedQuery: string;
  settledQuery: string;
  textHits: SearchHitResponse[];
  textSettled: boolean;
  search: UseQueryResult<ApiResponse<SearchResponse>>;
} {
  const trimmedQuery = query.trim();
  const settledQuery = useSettledQuery(trimmedQuery);
  const textSearchReady = settledQuery.length >= MINIMUM_SEARCH_CHARACTERS;
  const search = useQuery({
    queryKey: ["search", settledQuery],
    queryFn: () => searchDocuments(settledQuery, [], SEARCH_PAGE_LIMIT, SearchMatchMode.Prefix),
    enabled: textSearchReady,
    placeholderData: (previousData, previousQuery) =>
      keepPreviousTextResults(previousData, queryText(previousQuery?.queryKey), settledQuery),
  });
  const textHits = chooseShownTextHits(search.data?.body.hits, settledQuery, trimmedQuery);
  const textSettled = trimmedQuery === settledQuery && textSearchReady && !search.isFetching;
  return { trimmedQuery, settledQuery, textHits, textSettled, search };
}

/**
 * Keep the previous text hits only while the new query extends that search.
 * @param previousResults - The hits already on screen.
 * @param previousQuery - The query those hits belong to.
 * @param nextQuery - The query being typed.
 * @returns The previous hits when the new query continues them.
 * @throws Does not throw.
 */
export function keepPreviousTextResults<T>(
  previousResults: T | undefined,
  previousQuery: string | undefined,
  nextQuery: string,
): T | undefined {
  if (previousResults === undefined || previousQuery === undefined || previousQuery === "") {
    return undefined;
  }
  if (nextQuery.startsWith(previousQuery) && nextQuery !== previousQuery) {
    return previousResults;
  }
  return undefined;
}

/**
 * Choose the text hits that still belong on screen.
 * @param hits - The hits for the settled query.
 * @param settledQuery - The query those hits belong to.
 * @param liveQuery - The query in the field.
 * @returns The hits while the field still continues that query.
 * @throws Does not throw.
 */
export function chooseShownTextHits<T>(
  hits: T[] | undefined,
  settledQuery: string,
  liveQuery: string,
): T[] {
  if (hits === undefined || settledQuery === "") {
    return [];
  }
  if (liveQuery.startsWith(settledQuery)) {
    return hits;
  }
  return [];
}

/**
 * Read the query text from a search query key.
 * @param queryKey - The key, or none.
 * @returns The query text, or none when the key is not a search.
 * @throws Does not throw.
 */
function queryText(queryKey: readonly unknown[] | undefined): string | undefined {
  const text = queryKey?.[1];
  return typeof text === "string" ? text : undefined;
}

/**
 * Wait briefly before treating the query as ready.
 * @param query - The trimmed text the user is typing.
 * @returns The query after the pause.
 * @throws Does not throw.
 */
function useSettledQuery(query: string): string {
  const [settledQuery, setSettledQuery] = useState(query);
  if (query === "" && settledQuery !== "") {
    setSettledQuery("");
  }
  useEffect(() => {
    if (query === "") {
      return;
    }
    const timer = window.setTimeout(() => setSettledQuery(query), SEARCH_DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [query]);
  return query === "" ? "" : settledQuery;
}
