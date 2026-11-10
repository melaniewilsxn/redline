# Phase 3: Search

**Project:** Redline (see `docs/plans/build-plan.md`; section 5's "Behavior rules" apply)
**Audience:** the coding agent building this phase

Read and follow the `code-guidelines` skill before writing any code. If this plan and the guidelines disagree, the guidelines win: follow them and tell the user what differed.

Code snippets are hints, not ground truth. No new third-party libraries are needed. Stop the dev server after each checkpoint that starts it.

## Goal

Add search across documents. A hand-built, in-memory positional inverted index, split into paragraph chunks, answers multi-word and quoted-phrase queries. It ranks documents with BM25 and returns snippets with exact highlight offsets. The index is built from Postgres at startup. Every create and edit updates it after commit, and an edit re-indexes only the paragraphs it touched. Two endpoints expose it: `GET /search` (all documents or chosen ones) and `GET /documents/{id}/search`. A benchmark script compares the index with a naive scan on a 10MB contract and puts the numbers in the README.

The phase starts with the cleanup from the Phase 2 review (section 0).

**Out of scope:** AI retrieval (`search/retrieval.py`, phase 5), the exact/natural-language search toggle (phase 7), proposals (phase 4), and stemming, synonyms, or fuzzy matching (never: lawyers search exact words).

## Files

```
redline/
├── Makefile                                       # sections 0, 11
├── README.md                                      # section 12
└── backend/
    ├── src/redline/
    │   ├── main.py                                # section 9
    │   ├── search/
    │   │   ├── models.py                          # section 1
    │   │   ├── errors.py                          # section 1 (new)
    │   │   ├── tokenizer.py                       # section 2
    │   │   ├── chunker.py                         # section 3
    │   │   ├── query_parser.py                    # section 4
    │   │   ├── index.py                           # section 5
    │   │   ├── ranking.py                         # section 6
    │   │   ├── snippets.py                        # section 6
    │   │   └── query_runner.py                    # section 6 (new)
    │   ├── storage/document_repository.py         # section 7
    │   ├── services/
    │   │   ├── search_service.py                  # section 8
    │   │   └── document_service.py                # sections 0, 8
    │   └── api/
    │       ├── schemas.py                         # sections 0, 10
    │       ├── error_handlers.py                  # section 0
    │       ├── dependencies.py                    # section 9
    │       └── routes/
    │           ├── documents.py                   # section 9
    │           └── search.py                      # section 10
    ├── scripts/
    │   ├── __init__.py                            # new, empty
    │   ├── benchmark.py                           # section 11
    │   └── generate_large_document.py             # delete (section 11)
    └── tests/
        ├── api/test_documents_api.py              # section 0
        ├── api/test_search_api.py                 # section 13 (new)
        ├── large_documents/test_large_document_api.py  # section 0
        ├── large_documents/test_large_search.py   # section 13 (new)
        ├── search/
        │   ├── test_tokenizer.py                  # section 13 (new)
        │   ├── test_chunker.py                    # section 13 (new)
        │   ├── test_query_parser.py               # section 13 (new)
        │   ├── test_index.py                      # section 13 (new)
        │   ├── test_ranking.py                    # section 13 (new)
        │   ├── test_snippets.py                   # section 13 (new)
        │   └── test_query_runner.py               # section 13 (new)
        └── services/test_search_service.py        # section 13 (new)
```

## 0. Cleanup from the Phase 2 review

1. **One table for known errors.** `error_handlers.py` has ten near-identical handler functions, and each new error means another copy. Replace them with a table:

   ```python
   @dataclass(frozen=True)
   class KnownError:
       """How one failure class maps onto an error response."""
       exception_class: type[Exception]
       status: HTTPStatus
       error_type: ErrorType

   KNOWN_ERRORS = (
       KnownError(InvalidTargetError, HTTPStatus.UNPROCESSABLE_CONTENT, ErrorType.INVALID_TARGET),
       ...
   )
   ```

   `register_error_handlers` loops over `KNOWN_ERRORS` and registers `build_known_error_handler(known_error)`. That function returns a handler that logs and responds with that status and type. The validation, HTTP, and unexpected-error handlers stay separate, since each does something different. Adding an error becomes one line, which matters if the live session asks for a new rule.
2. **`build_error_response`** passes `asdict(body)` to `JSONResponse` instead of copying fields by hand.
3. **Test payloads use the request dataclasses.** In `tests/api/test_documents_api.py` and `tests/large_documents/test_large_document_api.py`, build `CreateDocumentRequest`, `ApplyChangesRequest`, `ChangeRequest`, and the target request types, and call `asdict` only at the HTTP call. `ChangeTargetType` values come from the enum. Tests that deliberately send invalid JSON (an unknown `type`, a wrong field) keep a raw dict, with a one-line comment saying why. The `post_document` and `patch_document` helpers lose their default arguments.
4. **`document_service.py`:** remove the `FIRST_VERSION` alias and use `INITIAL_DOCUMENT_VERSION` directly.
5. **`Makefile`:** add `PORT ?= 8000` and pass `--port $(PORT)` to Uvicorn in `dev`, so `make dev PORT=8002` works when 8000 is taken.

## 1. `search/models.py`

The search package imports `TextSpan` and `AppliedEdit` from `redline.editing.models`. These are pure engine types, so this doesn't break the "pure packages do no I/O" rule. Everything is frozen except `IndexedDocument` and `SearchIndex` in section 5.

| Class | Fields | Purpose |
|---|---|---|
| `Token` | `term: str`, `span: TextSpan` | one normalized word and where it sits |
| `TokenOccurrence` | `position: int`, `span: TextSpan` | a term's place in a chunk: token position (for phrases) and character span **relative to the chunk start** |
| `IndexedChunk` | `start: int`, `length: int`, `token_count: int`, `term_occurrences: dict[str, list[TokenOccurrence]]` | one paragraph; `start` is absolute in the document |
| `SearchPhrase` | `terms: list[str]` | a quoted phrase, normalized |
| `SearchQuery` | `terms: list[str]`, `phrases: list[SearchPhrase]` | parsed query; `terms` are unquoted, de-duplicated, in order |
| `AllDocuments` | none | search everything |
| `SelectedDocuments` | `document_ids: list[UUID]` | search these only |
| `Snippet` | `span: TextSpan`, `text: str`, `highlights: list[TextSpan]` | absolute offsets throughout |
| `SearchHit` | `document_id: UUID`, `title: str`, `version: int`, `score: float`, `match_count: int`, `snippets: list[Snippet]` | |
| `SearchPage` | `hits: list[SearchHit]`, `total_count: int` | |

`SearchScope = AllDocuments | SelectedDocuments`. Searching all documents and searching some are two cases of one type, not an optional list.

### `search/errors.py` (new)

- `SearchError(Exception)`: base class.
- `EmptyQueryError()`: the query has no words. Mapped to 422 `invalid_query`.
- `DocumentNotIndexedError(document_id: UUID)`: a selected document isn't in the index. Mapped to 404 `document_not_found`, the same response as a missing document elsewhere.

The search package raises its own errors, so it never imports from `storage`.

`term_occurrences` is a dictionary because looking a term up is the point of an inverted index. Its values are structured types (`list[TokenOccurrence]`), never dicts or `object`, which keeps it within the guidelines.

## 2. `search/tokenizer.py`

```python
WORD_PATTERN = re.compile(r"\w+(?:[-'’]\w+)*")
POSSESSIVE_SUFFIXES = ("'s", "’s")
```

- `tokenize(text: str) -> list[Token]`: every `WORD_PATTERN` match, in order. The span is the whole match, so `Company's` highlights in full. The term is `normalize_term(match)`.
- `normalize_term(word: str) -> str`: `casefold()`, then strip one trailing possessive suffix if present. `Company's` → `company`, `non-disclosure` → `non-disclosure`, `it's` → `it`.

The query parser uses the same `normalize_term`, so queries and documents always agree.

## 3. `search/chunker.py`

```python
PARAGRAPH_BREAK_PATTERN = re.compile(r"\n[ \t]*\n\s*")
MAXIMUM_CHUNK_CHARACTERS = 4000
```

`split_into_chunks(text: str, offset: int) -> list[TextSpan]`: split `text` into spans that **tile it exactly**, with no gaps and no overlaps. Each span is a paragraph plus the blank lines after it. A paragraph longer than `MAXIMUM_CHUNK_CHARACTERS` is split at the last whitespace before the limit, or at the limit if there's none. `offset` is added to every span, so a slice can be re-chunked in place (section 5). Empty text returns no spans.

Tiling is what makes incremental updates simple. Untouched chunks just move, and a re-chunked region fits exactly where the old one was.

## 4. `search/query_parser.py`

```python
PHRASE_PATTERN = re.compile(r'"([^"]*)"')
MAXIMUM_QUERY_CHARACTERS = 500
```

`parse_query(query_text: str) -> SearchQuery`:
- Each quoted part becomes a `SearchPhrase` of its tokens' terms. A quoted part with one word is treated as an unquoted term. An empty quoted part is dropped.
- The text outside quotes is tokenized into terms. An unmatched `"` is just a character, which the tokenizer ignores.
- Duplicate terms are removed, keeping first-seen order.
- No terms and no phrases raises `EmptyQueryError`. The API maps it to 422 `invalid_query`.

The route enforces `MAXIMUM_QUERY_CHARACTERS` with `Query(max_length=...)`.

## 5. `search/index.py`

```python
@dataclass
class IndexedDocument:
    """One document's chunks and term counts."""
    document_id: UUID
    title: str
    version: int
    text: str
    chunks: list[IndexedChunk]
    term_counts: dict[str, int]
    token_count: int

@dataclass
class SearchIndex:
    """Every indexed document, and which documents contain each term."""
    documents: dict[UUID, IndexedDocument]
    term_documents: dict[str, set[UUID]]
```

Text is kept in memory for snippets and incremental updates. That costs memory equal to the corpus size, which is fine here and is noted for Part II.

| Function | One job |
|---|---|
| `create_search_index() -> SearchIndex` | Return an empty index. |
| `index_chunk(text: str, span: TextSpan) -> IndexedChunk` | Tokenize the chunk's slice and build its occurrences, with positions counting from 0 and spans relative to `span.start`. |
| `index_document(index, document_id, title, version, text) -> None` | Chunk and index the whole text, then replace any earlier entry for this document. This is the full re-index. |
| `update_indexed_document(index, document_id, version, text, applied_edits) -> None` | The incremental path below. |
| `remove_document_terms(index, document) -> None` | Take a document's terms out of `term_documents` (used before re-indexing it). |
| `add_document_terms(index, document) -> None` | Put them back. |

**`update_indexed_document`**, with `text` the new text and `applied_edits` in pre-batch offsets:

1. Find the affected chunks. A chunk `[c_start, c_end)` is affected by an edit `[e_start, e_end)` when `c_start <= e_end` and `e_start <= c_end`. This is inclusive, so an insert on a boundary touches both neighbors. Add one neighbor chunk on each side of every affected chunk, because an edit can add or remove a blank line and merge or split paragraphs.
2. Group the affected chunk positions into runs of consecutive chunks.
3. Walk the old chunks in order with a running `shift` (the sum of `length_change` for edits that end at or before the current position):
   - an unaffected chunk is kept, with `start + shift`;
   - for a run, its old region is `[first.start, last.end)`. Its new region starts at `first.start + shift_before_run` and ends at `last.end + shift_before_run + change_within_run`, where `change_within_run` sums `length_change` for edits inside the run. Re-chunk `text[new_start:new_end]` with `split_into_chunks(..., offset=new_start)` and index each new chunk.
4. Rebuild `term_counts` and `token_count` by subtracting the removed chunks' counts and adding the new ones. Update `term_documents` for every term whose count crossed zero.
5. Store the new text and version.

The cost is proportional to the size of the touched paragraphs plus the number of chunks, not to re-tokenizing the whole document. The test in section 13 checks that the result is identical to a full `index_document` of the new text, which keeps this honest.

## 6. Ranking, snippets, and running a query

### `ranking.py`

```python
BM25_K1 = 1.2
BM25_B = 0.75
```

`score_bm25(index: SearchIndex, document: IndexedDocument, terms: list[str]) -> float`: standard BM25 over the whole document, where `terms` is the unquoted terms plus every phrase term, de-duplicated:
- `idf = ln(1 + (N - df + 0.5) / (df + 0.5))`, with `N = len(index.documents)` and `df = len(index.term_documents[term])`.
- `tf = document.term_counts[term]`; `dl = document.token_count`; `avgdl` is the mean `token_count` over the index.

Phrases count through their terms. A phrase match doesn't get an extra boost; that's a noted next step.

### `snippets.py`

```python
MAXIMUM_SNIPPETS_PER_HIT = 3
SNIPPET_LEADING_CHARACTERS = 80
SNIPPET_MAXIMUM_CHARACTERS = 240
```

- `find_chunk_highlights(chunk: IndexedChunk, query: SearchQuery) -> list[TextSpan]`: absolute spans of every unquoted term occurrence, plus every phrase match. A phrase match is a run of positions `p, p+1, ...` holding the phrase's terms in order, and its span runs from the first token's start to the last token's end. Sorted, and merged where they overlap.
- `build_snippet(text: str, chunk: IndexedChunk, highlights: list[TextSpan]) -> Snippet`: a window starting `SNIPPET_LEADING_CHARACTERS` before the first highlight, up to `SNIPPET_MAXIMUM_CHARACTERS` long, clipped to the chunk with its trailing blank lines removed. Edges are moved to whitespace without cutting a highlight. The snippet keeps only the highlights fully inside the window.

Snippets are the **first** matching chunks in document order, up to the maximum, like stepping through Find in Word. That also lets the scan stop early.

### `query_runner.py` (new)

`run_query(index: SearchIndex, query: SearchQuery, scope: SearchScope, limit: int, offset: int) -> SearchPage`, orchestrating:

1. **Candidates:** the scope's documents (`SelectedDocuments` ids not in the index raise `DocumentNotIndexedError`), intersected with `term_documents[term]` for every unquoted term and phrase term. Start the intersection with the rarest term.
2. **Phrase check:** for each candidate with phrases, keep it only if every phrase matches in at least one chunk.
3. **Hits:** for each match, `match_count` is the sum of `term_counts` for the unquoted terms, plus the number of phrase matches. Score with `score_bm25`.
4. **Order:** by score descending, then `document_id`, for stable paging. `total_count` is the number of matching documents.
5. **Snippets** are built only for the hits on the requested page.

## 7. `storage/document_repository.py`

Add `list_current_documents(connection) -> list[StoredDocument]`: every document with its current text, for building the index at startup. It uses the same join as `GET_DOCUMENT`, with no `WHERE`.

## 8. `services/search_service.py`

```python
class SearchService:
    """Owns the live index and keeps it consistent with committed writes."""
```

It holds one `SearchIndex` and one `threading.Lock`. Every method takes the lock: routes are sync and run on a thread pool, so reads and writes can overlap.

| Method | One job |
|---|---|
| `load_documents(self, documents: list[StoredDocument]) -> None` | Index every document (at startup). |
| `add_document(self, document: StoredDocument) -> None` | Full index of a new document. |
| `update_document(self, document: StoredDocument, applied_edits: list[AppliedEdit], base_version: int) -> None` | If the indexed version equals `base_version`, call `update_indexed_document`. Otherwise log a warning and call `index_document`. Any exception from the incremental path is logged with `logger.exception`, and the document is fully re-indexed instead. If that also fails, log the error and leave it: the database write already succeeded, and the request must not fail because of the index. |
| `search(self, query_text: str, scope: SearchScope, limit: int, offset: int) -> SearchPage` | `parse_query`, then `run_query`. |

Log entry and exit for `load_documents` (count, time taken), `update_document` (document id, both versions, which path was taken), and `search` (term and phrase counts, scope type, hit count). Never log the query text: a search can contain confidential contract wording.

### `document_service.py`

`create_document` and `apply_document_changes` take a `search_service: SearchService` argument. Each calls the service **after** its transaction block commits: `add_document`, or `update_document(stored, edited.applied_edits, expected_version)`. This is the write path from the behavior rules.

`scripts/seed.py` writes straight to the database, so a running server won't see seeded documents until it restarts. The README says to seed before `make dev`, or to restart after seeding. The seed script builds its own throwaway `SearchService` to satisfy the new argument.

## 9. Wiring

- **`main.py` lifespan:** after the schema is applied, build a `SearchService`, call `load_documents(list_current_documents(connection))`, and store it on `app.state.search_service`. Log the document count and the build time.
- **`dependencies.py`:** `get_search_service(request: Request) -> SearchService` returns `request.app.state.search_service`. This is a FastAPI dependency, not a thin helper: routes need it to receive the service and tests need it to override.
- **`routes/documents.py`:** `create_document` and `apply_changes` take the service through `Depends(get_search_service)` and pass it on.

## 10. Search API

### `api/schemas.py`

Add `ErrorType.INVALID_QUERY = "invalid_query"`, and two `KNOWN_ERRORS` rows: `EmptyQueryError` → 422 `invalid_query`, and `DocumentNotIndexedError` → 404 `document_not_found`.

| Class | Fields |
|---|---|
| `TextSpanResponse` | `start: int`, `end: int` |
| `SnippetResponse` | `start: int`, `end: int`, `text: str`, `highlights: list[TextSpanResponse]` |
| `SearchHitResponse` | `document_id: UUID`, `title: str`, `version: int`, `score: float`, `match_count: int`, `snippets: list[SnippetResponse]` |
| `SearchResponse` | `hits: list[SearchHitResponse]`, `total_count: int`, `limit: int`, `offset: int` |

Highlight offsets are absolute in the document, so the UI can jump straight to them.

### `routes/search.py`

| Method and path | Query parameters | Success |
|---|---|---|
| `GET /search` | `q` (1 to 500 characters, required), `document_ids` (repeatable: `?document_ids=a&document_ids=b`), `limit` 1 to 100 (default 20), `offset` ≥ 0 | 200 `SearchResponse` |
| `GET /documents/{document_id}/search` | `q`, `limit`, `offset` | 200 `SearchResponse`; 404 if the document isn't indexed |

`GET /search` builds `SelectedDocuments` when `document_ids` is given and non-empty, else `AllDocuments`. The parameter is declared as `Annotated[list[UUID], Query()] = []`: an empty list is the natural "not given" value for a repeatable parameter, so no optional is needed. Reuse the page-limit constants from `routes/documents.py` by moving them to `api/schemas.py`, where both routers import them.

Include the router in `main.py`.

## 11. Benchmark

Delete `scripts/generate_large_document.py`. The test fixture `tests/fixtures/large_contract.py` already builds the 10MB contract, and the benchmark reuses it.

`scripts/benchmark.py`, run as a module from `backend/` so `tests.fixtures` imports (`make bench`: `cd backend && uv run python -m scripts.benchmark`). Use `time.perf_counter`, run each case `BENCHMARK_REPEATS = 5` times, and report the median. No database.

| Case | Indexed | Naive baseline |
|---|---|---|
| Build index for the 10MB contract | `index_document` | — |
| Rare phrase: `"Schedule {n} to the Customer"`, with `n` the section number about 90% of the way through the contract (read from the text, not hard-coded) | `run_query` | case-insensitive regex scan of the whole text |
| Common word: `customer` | `run_query` | regex scan with `\b` boundaries |
| Common phrase: `"written notice"` | `run_query` | regex scan |
| Two words, both must appear: `supplier rejected` | `run_query` | two regex scans |
| Update after 1 edit | `update_indexed_document` | `index_document` of the new text |
| Update after 100 spread edits | `update_indexed_document` | `index_document` |
| Apply 1,000 range changes | `apply_changes` | — |

Also run one cross-document case: an index of 20 documents, each `build_large_contract(500 * 1024)`, with the sentence "The Escrow Agent shall release the Holdback Amount." appended to document 7 only. Query `"escrow agent" holdback` indexed, against a regex scan of all 20 texts. This shows the index skipping the 19 documents that can't match. Print a Markdown table: case, indexed ms, naive ms, speedup. `main()` is the process boundary: catch, log, exit non-zero.

Expect the index to win clearly on rare terms, phrases, and cross-document pruning. On a single 10MB document with a very common word, snippet and count work can bring it close to a raw regex scan. Report honestly whatever the numbers show; the README explains why.

## 12. README

- **Usage:** add search examples, covering a word, two words, a quoted phrase, `document_ids`, and per-document search. Add them to `samples/curl_requests.sh` as new steps, including an empty query → 422 `invalid_query`.
- **API design:** the search endpoints and why search is `GET` with query parameters.
- **Search design** (new section): tokenization (case folding, hyphens kept, possessives dropped, no stemming, and why), AND semantics and phrases within a paragraph, BM25 at document level, paragraph chunks with chunk-relative positions, incremental re-indexing after commit with the version check and full re-index fallback, the lock, and memory (the corpus text is held in memory).
- **Performance:** the benchmark table and a short reading of it.
- **Setup:** seed before `make dev`, or restart after seeding.
- **Next steps:** add the phrase-match boost, a term → chunk map to skip chunk scans for common words, a persistent or external index (Postgres full-text search or OpenSearch) for multiple servers, and the search mode toggle.

## 13. Tests

The guidelines' test structure applies. Search unit tests are pure: no database, small literal texts.

### `tests/search/test_tokenizer.py`

- `test_tokens_are_case_folded`
- `test_token_spans_cover_the_original_word`
- `test_possessive_is_dropped_from_term_but_kept_in_span` (`Company's`)
- `test_curly_possessive_is_dropped` (`Company’s`)
- `test_hyphenated_word_is_one_token`
- `test_punctuation_splits_tokens` (`(30)` → `30`)
- `test_word_without_possessive_is_unchanged`

### `tests/search/test_chunker.py`

- `test_chunks_tile_the_text_exactly` (the spans join back to the full text, with no gaps)
- `test_blank_line_separates_paragraphs`
- `test_single_newline_does_not_split`
- `test_long_paragraph_splits_at_whitespace_before_limit`
- `test_long_paragraph_without_whitespace_splits_at_limit`
- `test_offset_shifts_every_span`
- `test_empty_text_has_no_chunks`

### `tests/search/test_query_parser.py`

- `test_unquoted_words_become_terms`
- `test_quoted_words_become_a_phrase`
- `test_single_word_in_quotes_becomes_a_term`
- `test_duplicate_terms_are_removed_in_order`
- `test_unmatched_quote_is_ignored`
- `test_query_with_no_words_raises_empty_query_error`
- `test_query_terms_are_normalized_like_document_terms` (`Company's` → `company`)

### `tests/search/test_index.py`

- `test_index_document_records_term_documents`
- `test_index_document_twice_replaces_earlier_entry`
- `test_chunk_occurrences_use_chunk_relative_spans`
- `test_incremental_update_matches_full_reindex_for_edit_inside_paragraph`
- `test_incremental_update_matches_full_reindex_for_edit_removing_paragraph_break` (two paragraphs merge)
- `test_incremental_update_matches_full_reindex_for_edit_adding_paragraph_break`
- `test_incremental_update_matches_full_reindex_for_insert_at_chunk_boundary`
- `test_incremental_update_matches_full_reindex_for_edits_in_separate_paragraphs`
- `test_term_removed_by_edit_leaves_term_documents`
- `test_term_added_by_edit_joins_term_documents`

Each "matches full reindex" test compares the updated `IndexedDocument` with a freshly indexed one: chunk spans, `term_occurrences`, `term_counts`, `token_count`. It also compares `term_documents` across the two indexes.

### `tests/search/test_ranking.py`

- `test_rarer_term_scores_higher` (with equal counts, the document holding the rarer term ranks first)
- `test_more_occurrences_score_higher`
- `test_longer_document_scores_lower_for_same_count`

### `tests/search/test_snippets.py`

- `test_term_highlights_are_absolute_offsets`
- `test_phrase_highlight_spans_the_whole_phrase`
- `test_phrase_terms_out_of_order_do_not_highlight`
- `test_overlapping_highlights_are_merged`
- `test_snippet_does_not_cut_a_highlight`
- `test_snippet_stays_inside_its_chunk`

### `tests/search/test_query_runner.py`

- `test_document_missing_one_term_is_excluded` (AND semantics)
- `test_document_with_all_terms_is_included`
- `test_phrase_matches_consecutive_words`
- `test_phrase_does_not_match_across_paragraphs`
- `test_phrase_words_apart_do_not_match`
- `test_selected_documents_limit_the_scope`
- `test_selected_unknown_document_raises_document_not_indexed_error`
- `test_hits_are_ordered_by_score`
- `test_paging_applies_limit_and_offset`
- `test_match_count_includes_terms_and_phrases`
- `test_snippets_are_the_first_matching_chunks_in_document_order`

### `tests/services/test_search_service.py`

- `test_update_with_matching_base_version_uses_incremental_path` (check the result with a search)
- `test_update_with_other_base_version_reindexes_document`
- `test_update_recovers_when_incremental_update_raises` (monkeypatch `update_indexed_document` to raise; the document is still searchable at its new text)

### `tests/api/test_search_api.py`

- `test_search_finds_created_document`
- `test_search_reflects_patch_immediately` (a removed word stops matching, an added word starts)
- `test_search_with_document_ids_limits_results`
- `test_document_search_returns_only_that_document`
- `test_document_search_for_missing_document_returns_404`
- `test_empty_query_returns_422_invalid_query` (`q=""` fails validation; a query of only punctuation, `q=%22%22`, returns `invalid_query`. Assert each `error_type`.)
- `test_query_over_maximum_length_returns_validation_error`
- `test_highlight_offsets_point_at_the_matched_text` (slice the document text at each highlight and check the word)
- `test_index_is_built_from_database_at_startup`: commit a document through a separate connection (not the rolled-back one), start a fresh client, search for it, then delete it in a `finally` block. This is the one test that commits, because the startup path reads committed data. Use a unique title, and assert only on that document.

### `tests/large_documents/test_large_search.py`

- `test_incremental_update_matches_full_reindex_on_large_document`: index the 10MB contract, apply the 1,000-change batch from Phase 1, run `update_indexed_document`, and compare with `index_document` of the result.
- `test_phrase_near_end_of_large_document_is_found` (with the highlight offset checked against the text)

## 14. Design notes (for the README)

- **Why build the index.** The prompt asks for one, and the off-the-shelf BM25 libraries don't track positions or support incremental updates.
- **Chunks and relative positions.** Positions are stored relative to their paragraph, so an edit moves later paragraphs by changing one number each, instead of rewriting every posting after the edit.
- **Re-index after commit.** The database is the source of truth. If the index update fails, the request still succeeds, and the index repairs itself with a full re-index of that document.
- **AND semantics.** Lawyers expect every word they type to be in the result. A looser natural-language mode is a planned toggle.
- **Trade-offs:** memory equal to the corpus, a single process (the index isn't shared between servers), and chunk scans for very common words.

## Checkpoints ✅

Stop at each checkpoint and report before going on.

1. **Cleanup.** Section 0 is done. `make lint` and `make test` pass. Report the test count and the new `KNOWN_ERRORS` table.
2. **Pure search pieces.** Tokenizer, chunker, parser, ranking, snippets, and the full `index_document` path. Run `uv run pytest tests/search -v` (excluding the incremental tests) and report.
3. **Incremental updates.** `update_indexed_document` and its tests, including the 10MB comparison. Report the results and the 10MB test's duration.
4. **Service and API.** `make test` passes. Start `make dev` (use `PORT=8002` if needed) after `make seed`, and report the startup log line with the indexed document count and build time, plus one search request's log lines.
5. **Benchmark and docs.** `make bench`: paste the table. Run `bash samples/curl_requests.sh`: report the new search steps' status codes. Report the README's section headings.
6. **Final.** `make lint` and `make test` totals.

## Definition of done

- [ ] Section 0 cleanup is done, including the `KNOWN_ERRORS` table and dataclass test payloads.
- [ ] The `search` package has the section 1 to 6 modules, imports only the standard library, `redline.editing.models`, and its own modules, and does no I/O.
- [ ] The index is built at startup and updated after every create and edit commit, incrementally when the version matches, with the full re-index fallback.
- [ ] `GET /search` and `GET /documents/{id}/search` work as in section 10, with errors in the standard format.
- [ ] No log line contains query text or document text.
- [ ] Every test named in section 13 exists and passes; tests leave the test database as they found it.
- [ ] `make bench` prints the table, and the README has the search design and the numbers.
- [ ] Each checkpoint was reported.
