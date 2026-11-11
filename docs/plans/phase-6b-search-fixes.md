# Phase 6b: Search Fixes

**Project:** Redline (see `docs/plans/build-plan.md`). Do this **before** Phase 7.
**Audience:** the coding agent building this phase

Read and follow the `code-guidelines` skill before writing any code. If this plan and the guidelines disagree, the guidelines win: follow them and tell the user what differed. Leave `docs/infra.md` alone.

## What's wrong

Found by hand-testing the running app. The API returns correct results in 3–14 ms. The problems are how the UI uses it.

1. **Partial words never match.** The index matches whole words only, so typing "Ma" or "Mas" in the left search shows "No matches" until the whole word "Master" is typed. In a search-as-you-type box this reads as broken.
2. **The left search ignores contract names.** It only searches contract text, so typing a contract's name, the first thing anyone tries, finds nothing until the whole word appears in the body.
3. **Bug: in-contract search can't reach most matches.** `DocumentView` reuses the cross-document search endpoint, which returns at most 3 snippets per document. The header shows `match_count` ("56 matches" for "customer" in the MSA), but Previous and Next step through `snippets` (at most 3), and only those snippets' highlights are marked. It also uses word-AND semantics: "Customer shall" reports 99 (every "Customer" plus every "shall"), not the phrase. And every pause in typing waits 250 ms, then makes a network round trip, for text the browser already has.

## Goal

- **Left search:** instant contract-name filtering, plus full-text results where the last word being typed matches as a prefix.
- **In-contract search:** a true find-in-page that runs in the browser on the loaded text, matches literally, highlights every match, and steps through all of them.
- **The API stays exact by default.** Prefix matching is an explicit opt-in.

## 1. Backend: an opt-in prefix mode

- **`search/models.py`:** a `SearchMatchMode(StrEnum)` with `EXACT = "exact"` and `PREFIX = "prefix"`. `SearchQuery` gains `prefix_terms: list[str]`, which is empty unless prefix mode applies. This avoids an optional field.
- **`query_parser.py`:** `parse_query(query_text, match_mode)`. A query with only a prefix term ("Mas") is **not** empty: `EmptyQueryError` requires no terms, no phrases, and no prefix terms, and `find_candidates` handles an empty `terms` list when prefix terms exist. In `PREFIX` mode, if the raw query doesn't end in whitespace or a closing quote, its **last unquoted term** moves from `terms` to `prefix_terms`. Everything else parses as today. In `EXACT` mode, `prefix_terms` is always empty.
- **`index.py`:** `find_terms_with_prefix(index, prefix, limit) -> list[str]` returns vocabulary terms starting with `prefix`, the most widespread first (by the size of their `term_documents` entry), capped at `MAXIMUM_PREFIX_EXPANSIONS = 50`. A linear scan of the vocabulary keys is fine at this size.
- **`query_runner.py`:** for each prefix term, a document must contain **at least one** of its expansions; that is the candidate union, intersected with the other terms as usual. Scoring adds BM25 for every expansion present in the document. Highlights and `match_count` include every expansion's occurrences. A prefix term with no expansions means no results.
- **API:** `GET /search` and `GET /documents/{id}/search` take `mode: SearchMatchMode = SearchMatchMode.EXACT`, passed through the search service. Document `mode=prefix` in the README's API design section: "for search-as-you-type; the last unquoted word matches as a word prefix".
- **Tests:**
  - `tests/search/test_query_parser.py`:
    - `prefix mode moves the last unquoted term to prefix terms`
    - `prefix mode keeps the last term exact after trailing whitespace`
    - `prefix mode leaves a trailing quoted phrase exact`
    - `exact mode never produces prefix terms`
  - `tests/search/test_index.py`:
    - `finds terms with a prefix, most widespread first`
    - `caps prefix expansions`
  - `tests/search/test_query_runner.py`:
    - `prefix term matches a document containing any expansion`
    - `prefix term with no expansions matches nothing`
    - `prefix highlights cover every expansion`
    - `exact word plus prefix term both must match` (the "written not…" case)
  - `tests/search/test_query_parser.py` also: `prefix-only query is not empty`
  - `tests/api/test_search_api.py`:
    - `search with prefix mode finds a partial word`
    - `search defaults to exact mode` ("Mas" returns nothing without `mode`, on both `/search` and `/documents/{id}/search`)

## 2. Left search: names and text together

- `searchDocuments` gains a `mode` argument. The left search always sends `SearchMatchMode.Prefix` (constant object in `api/types.ts`, from the generated schema).
- **Two groups in the results** while a query is active:
  1. **Contracts:** contracts whose **title** contains the query, case-insensitive, filtered in the browser from the already-loaded document list. It works from the first character, with no request. Clicking one opens it.
  2. **In contract text:** the server results as today (snippets, jump to match), which start at 2 characters.

  Each group has a small heading (Instrument Sans 12px/500, muted) and is hidden when empty. With both empty: "No contracts or text match “{query}”."
- **Debounce** drops to `150` ms. While a request is in flight, the previous text results stay visible **only when the new query extends the previous one** ("inde" to "indem"), the normal typing case. If the query changes to something else, drop the old hits right away, so no results are ever shown under the wrong query.
- The results view replaces the contract list from the first character. With one character, text search hasn't run, so an empty view says "No contract names match “{query}”" and doesn't claim the text was searched.

## 3. In-contract search: client-side find

Replace `useDocumentSearch` in `DocumentView` with a pure in-browser find. The text is already loaded, so this is instant and exact.

- **`features/redline/find_in_text.ts`:** `findTextMatches(text, query, limit)` returns every non-overlapping, case-insensitive, **literal** occurrence of `query` as `TextSpan`s, in order, stopping at `MAXIMUM_FIND_MATCHES = 1000`. It returns `{ matches, capped }`. An empty or whitespace-only query returns no matches. Quotes are literal characters here; Cmd-F semantics.
- **`DocumentView`:**
  - The match index steps through **all** matches.
  - The header shows "{current} of {total}", "{current} of 1000+" when capped, or "No matches".
  - Every match is highlighted, and the current one gets the ring and is scrolled into view.
  - `Enter` / `Shift+Enter` and Previous/Next wrap around. `Esc` in the contract's find field clears that find only, not the left search. The global Escape handler must not also fire from inside that field.
  - The match index resets to the first match when the query changes, and stays in range when the text changes (for example after Apply).
  - Find compares the **saved** text literally (not as a regular expression). Highlights reuse the existing mark rendering, including text inside a pending suggestion's original words. Words that exist only in an unapplied insertion aren't matches.
- No debounce: matching 10MB of text in the browser takes a few milliseconds, and the result list is capped.
- The server's `GET /documents/{id}/search` stays as an API endpoint; the UI just no longer uses it for find. Remove `useDocumentSearch` if nothing else uses it.
- **Tests, in `find_in_text.test.ts`:**
  - `finds every case-insensitive occurrence`
  - `matches partial words literally`
  - `matches a multi-word phrase literally, not as separate words`
  - `does not return overlapping matches`
  - `caps the matches and reports it`
  - `returns no matches for a blank query`

  In `review_flow.test.tsx`:
  - `in-contract find steps through every match` (a document with 5 occurrences: Next 5 times wraps back to "1 of 5")

## 4. README

Update **Search design** to cover two searches, each fitting its job:
- **Across contracts:** the server index. Exact whole words by default, for precise clause hunting, with `mode=prefix` for search-as-you-type. Plus instant name filtering in the UI.
- **Within an open contract:** find-in-page in the browser, because the text is already there. It's literal and instant, and reaches every match.

## Checkpoints ✅

Stop at each checkpoint and report before going on.

1. **Backend.** `make test` and `make lint` totals, plus a timing check: `GET /search?q=indemn&mode=prefix` and `q=Mas&mode=prefix` against the running server, showing hits and milliseconds. `make ui-types` afterwards.
2. **UI.** In a visible browser, report screenshots of:
   - typing "Mas" in the left search: the MSA under Contracts, and text matches below;
   - "indemn": matches for "indemnify" and "indemnity";
   - in the MSA, find "customer" showing "1 of 56" and stepping with Next;
   - "Customer shall" counting the phrase, not the separate words.

   `make ui-test` and `make ui-lint` totals.
3. **Final.** README updated, commit and push.

## Definition of done

- [ ] The left search shows matching contract names instantly and full-text matches where the last word matches as a prefix; the API stays exact unless `mode=prefix`.
- [ ] In-contract find runs in the browser, matches literally, highlights every match, and steps through all of them.
- [ ] Every named test passes, lint is clean, the README explains both searches, and it's pushed.
