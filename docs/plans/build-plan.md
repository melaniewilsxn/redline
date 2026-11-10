# Redline: Build Plan

## 1. Goal

Redline is a document redlining and search service for lawyers. Users edit contract text through a JSON API, search clauses and phrases across documents, and ask an LLM for playbook-style redline suggestions, each checked against the document and carrying a rationale, which a reviewer accepts or rejects. A React review UI ("Word's review pane, but better") sits on top.

Built for the Sandstone take-home (Part I). The infra write-up for Part II lives in `docs/infra.md`.

## 2. MVP

### Must have (the assessment baseline, built first)

- **Change requests:** `PATCH /documents/{id}` takes a list of changes and returns the updated text. A change targets text by character range, by text plus occurrence number, or by text plus surrounding context.
- **Atomic batch edits:** every target in a request is resolved first. Any overlap or unresolvable target rejects the whole request with a 4xx, and nothing is applied. The document is rebuilt in a single linear pass.
- **Search:** across all documents, a chosen set (`document_ids`), or one document, returning ranked snippets with highlight offsets. Supports multi-word queries and quoted exact phrases (rules in section 5).
- **Versioning and concurrency:** each write creates a new version. Reads return an `ETag`. Writes require `If-Match` and return `412` when stale.
- **Errors:** 4xx for client errors and 5xx for server errors, always as JSON `{ "error": string, "code": number, "error_type": string }` (section 4).
- **Tests:** unit tests for the editing engine and the search index, large-document (10MB) tests, and a benchmark script.
- **Docs:** README (setup, usage, performance, API design rationale) and a curl sample script.

### Should have (what makes it a redlining product)

- **AI redline suggestions:** given an instruction, with the playbook as context, the LLM returns structured suggestions. Each is anchored and checked by the editing engine, so the model never edits text directly. Suggestions aren't stored: the reviewer accepts or rejects each one in the UI, then applies the accepted ones as one `PATCH` of range targets against the version they were computed on.
- **Review UI:** document list, the document with suggestions shown as inline redlines, a changes panel with accept and reject, search with jump-to-match, an AI instruction box, and keyboard review (next, previous, accept, reject).

**Scope change at the 3-hour mark:** stored proposals (with rebasing on every write) and version compare moved to "left for later" so the graded LLM integration and a polished UI fit. The rebase algorithm is already built and tested in `editing/rebase.py`; what's deferred is storing proposals and wiring rebase into the write path.

### Deliberately left for later (documented as next steps in the README)

- Auth, users, and per-document permissions (the author is a plain name field).
- Rich text and .docx import/export. Documents are plain text.
- Stored proposals: a `proposals` table, propose/accept/reject endpoints, and rebasing pending proposals on every write (the algorithm exists in `editing/rebase.py`, with tests). The design is kept in section 5's behavior rules.
- Version compare (a word-level blackline between two versions).
- Comment threads separate from suggestion rationales.
- Embedding-based semantic search and hybrid re-ranking.
- Multi-pattern target resolution (Aho–Corasick) for very large batches of text-targeted changes.
- Multi-process deployment. The search index is in-process memory, which assumes a single server (covered in Part II).
- Storing versions as deltas instead of full copies.

## 3. Architecture

```mermaid
flowchart LR
    UI[React review UI] -->|JSON over HTTP| API[api: FastAPI routes, ETags, error mapping]
    Curl[curl / tests] --> API
    API --> Services[services: one per use case]
    Services --> Editing[editing: anchors, atomic apply, rebase]
    Services --> Search[search: chunked positional index, BM25, snippets]
    Services --> AI[ai: redline suggester]
    AI -->|structured JSON output| LLM[(Anthropic API)]
    AI -->|retrieve relevant clauses| Search
    Services --> Storage[storage: psycopg + plain SQL]
    Storage --> DB[(PostgreSQL)]
```

A request enters through `api`, which validates the payload, checks `If-Match`, and calls one service for a write. Reads that are a single query call the repository directly, since a service that only forwards a call adds nothing. Services orchestrate and hold no business logic. `editing` and `search` are pure, with no I/O, so they are fast to unit test. On a write, the service loads the version named by `If-Match` and asks `editing` to resolve and apply the changes. This happens outside any transaction, so a large rebuild never holds a lock. It then commits in one transaction (rules in section 5): bump the version with a compare-and-swap and insert the new version. Only after commit does it tell `search` which ranges changed, so it re-indexes just those chunks. On startup the search index is rebuilt from the latest version of every document in Postgres. For AI redlines, a short document goes to the model whole; for a large one, a retrieval function ranks its paragraphs against the instruction, so 10MB documents never go to the model whole. The service sends the text plus the playbook to the LLM and runs each suggestion through `editing`'s anchor resolution before returning it.

## 4. Key decisions

| Decision | Choice | Main alternative | Why this one |
|---|---|---|---|
| Backend language | Python 3.14 | TypeScript | Your preference. 3.14 rather than 3.15 because 3.15 is only weeks old and library wheels can lag. |
| Web framework | FastAPI, served by Uvicorn | Flask, Litestar | Async, automatic OpenAPI docs (a free API explorer for reviewers), and it validates standard `@dataclass` request bodies, so the code can follow the dataclass rule. Uvicorn is the server process that listens on the port and hands requests to FastAPI. |
| Package and tool management | uv, Ruff, pytest | pip + venv, Black | Fast, one lockfile, one formatter and linter. |
| Storage | PostgreSQL through `psycopg` 3 (no ORM), schema in a `.sql` file, queries as plain SQL in the repositories | SQLite; an ORM such as SQLAlchemy | Handles many concurrent writers with row-level locks, where SQLite allows one writer at a time. It is the production database, so Part II describes the same system. Plain SQL keeps every query readable. Reviewers start it with `docker compose up`. |
| Version storage | Full text per version | Diffs per version | Simple and correct for a prototype. The cost at 10MB times many versions is called out in the README and Part II. |
| Change targeting | Three target types: range, text + occurrence, text + context (prefix/suffix, like the W3C TextQuoteSelector) | Range only | Lawyers' edits are about wording, not offsets. Context matching keeps an edit on the right clause when the same phrase appears many times. |
| Batch apply | Resolve all targets, sort, reject overlaps, rebuild once with string slices joined in one pass | Apply changes one at a time | O(n + k) instead of O(n x k), and atomic: either every change applies or none does. |
| Proposal anchoring | Store a range kept current by rebasing it through every applied edit, plus the original text as a check | Re-find the quoted text after every edit | Exact and linear. Every edit already goes through the engine, so the shifts are known. A proposal whose text was edited underneath it is marked stale instead of guessing. |
| Concurrency | Integer version; ETag `"{document_id}-{version}"`; `If-Match` required (428 if missing, 412 if stale). The first statement of the write transaction is a compare-and-swap: `UPDATE documents SET current_version = v + 1 WHERE id = ... AND current_version = v`, and zero rows updated means rollback and 412. | Last write wins; `SELECT ... FOR UPDATE` while computing the edit | The prompt asks for it, and it matches how lawyers lose work: two people editing the same draft. Doing the compare-and-swap first locks the row, so a racing writer fails before inserting anything, and the edit is computed before the transaction so no lock is held during it. |
| Error format | `{ "error": "<readable message>", "code": <HTTP status>, "error_type": "<stable code>" }` | `error` holding the stable code | Keeps the prompt's two fields, readable in curl output, while clients and tests branch on `error_type` (an enum). |
| Change JSON | Each change has a required `type`: `range`, `occurrence`, or `context`, mapping to three engine dataclasses | Infer the target type from which fields are present | Explicit, and validation errors name the problem. If FastAPI cannot validate the dataclass union, the route maps the JSON onto the dataclasses itself. |
| Search index | Custom in-memory positional inverted index, chunked by paragraph, with chunk-relative positions | Whoosh/Tantivy; `rank_bm25`; full rescan | Deliberate exception to "use a library": the prompt asks us to build and discuss one, and `rank_bm25` has no positions or incremental updates. Chunk-relative positions mean an edit re-indexes only the touched paragraphs and shifts the starts of later chunks. |
| Ranking | BM25 (k1 = 1.2, b = 0.75) | TF-IDF | The standard baseline. Easy to explain. |
| Tokenization | Lowercased word tokens with character offsets. Internal hyphens stay (`non-disclosure` is one token). A trailing possessive `'s` or `’s` is dropped from the indexed term, while the highlight covers the whole word. No stemming or stopword removal. | Stemming; keeping `company's` as its own term | Lawyers need exact words ("shall" vs "may"), but a search for the defined term "Company" must find "the Company's obligations". Offsets make highlighting exact. |
| Search semantics | Every unquoted term must appear somewhere in the document; quoted phrases must appear as consecutive tokens within one paragraph. BM25 scores the whole document from term counts summed across its chunks. One hit per document, with snippets. | Any term matches (OR); scoring each paragraph separately | Matches how lawyers search: precise, not fuzzy. One hit per document keeps cross-document results readable. |
| AI retrieval | A separate function that ranks paragraph chunks by BM25 over the instruction's content words, with any term matching, and returns the top chunks | Reusing user search | "Make indemnification mutual" would find nothing if every word had to match. User search stays exact. |
| Phrase queries | Quoted phrases match consecutive positions within a chunk | No phrases | Exact clause wording is how lawyers search. Phrases do not cross paragraph boundaries, which matches how clauses are written. |
| Version compare (deferred) | `difflib.SequenceMatcher` on word tokens | `diff-match-patch` | Standard library, word-level output. The quadratic worst case is acceptable for comparing contract versions; noted as a risk for 10MB. |
| LLM | Anthropic Python SDK, `claude-sonnet-5-5`, JSON outputs through `output_config.format` with a JSON schema (no beta header, no forced tool choice), `thinking: between_tools` and `medium` effort so the token budget goes to the answer | Tool use; free text parsed with regex | The response is constrained to the schema, so it parses reliably. Every suggestion is anchored and checked by the engine, never applied directly. |
| LLM in tests | A `RedlineModelClient` protocol with a fake for tests | Mocking the SDK | Tests are deterministic and offline. The real client is used only at runtime. |
| API shape | Resources for reads and writes; `POST /documents/{id}/ai-redlines` as an action | `GET` for suggestions | Suggesting is an expensive, non-repeatable computation with an instruction body, so it's a `POST` action. Accepting goes through the normal `PATCH`. |
| Applying AI suggestions | The reviewer accepts or rejects each suggestion in the UI, then applies the accepted ones as one `PATCH` of range targets, with `If-Match` set to the `ETag` the suggestions were computed against | Storing suggestions as proposals; one `PATCH` per accept | The ranges are exact for that version, anchoring guarantees the batch has no overlaps, and a changed document becomes a clean 412. No new tables. |
| Frontend | React 19 + Vite + TypeScript, TanStack Query, CSS Modules | Next.js; Tailwind | Single-page app with no server rendering needed. TanStack Query handles caching and refetching after writes. CSS Modules keep all styling in stylesheets. |
| UI build order | Functional UI first, design pass last | Design first | Your style: a solid foundation, then polish. |

## 5. Data model

Exact schemas belong in each phase plan.

**Storage (PostgreSQL)**

- `documents`: one row per document, with its title, current version number, and timestamps.
- `document_versions`: the full text of each version, with the author and a short summary of what changed (for example "Accepted 3 proposals"). The current text is the row whose version equals `documents.current_version`.
- `proposals`: a pending or resolved change, with its document, its current range, the original text it covers, the replacement, the prefix and suffix context, author, rationale, status (`ProposalStatus`: pending, accepted, rejected, stale), the version it was created on, and when it was resolved.

**Engine types (dataclasses, in `editing`)**

- `RangeTarget`, `OccurrenceTarget`, `ContextTarget`: the three ways to point at text. A change's target is a union of the three.
- `Change`: a target plus replacement text.
- `ResolvedChange`: a change pinned to an exact start and end.
- `AppliedEdit`: where an edit landed and how much the length changed. Used for rebasing proposals and for incremental re-indexing.

**Search types (in `search`)**

- `Chunk`: a paragraph-sized span of one document, with its start offset and its own postings (term to positions).
- `SearchQuery`: the parsed query, its terms and its quoted phrases.
- `SearchHit`: document, score, and snippets. `Snippet`: text with highlight ranges in absolute document offsets.

**AI types (in `ai`)**

- `PlaybookPosition`: a clause topic, preferred position, acceptable fallbacks, and positions never accepted.
- `RedlineSuggestion`: the model's structured output (quoted target with context, replacement, rationale), before it is validated.

### Behavior rules

These are settled. Phase plans implement them as written.

**Editing**

- Ranges are half-open `[start, end)` character offsets. Occurrence numbers start at 1. Text matching for anchors is case-sensitive.
- An empty replacement deletes. A zero-width range inserts.
- Changes in a batch are sorted by `(start, end)`. Changes that only touch at an edge both apply, so an insert at the start of a replaced range goes before it. Two zero-width inserts at the same position are rejected as overlapping, because their order would be arbitrary.
- `AppliedEdit` offsets refer to the text before the batch.

**Writes** (the proposal rules here are kept for the deferred proposals feature)

- Apply, propose, and accept all require `If-Match`. Anchors resolve against that version. Author is required on apply and propose.
- Apply and accept: compute the edit outside the transaction, then in one transaction: (1) the compare-and-swap on `documents` (zero rows → rollback, 412), (2) insert the `document_versions` row (unique on `document_id, version`), (3) rebase pending proposals, and for accept, mark that proposal accepted.
- Propose: in one transaction, lock the document row with `SELECT ... FOR SHARE`, confirm the version still matches (else 412), and insert the proposals with their prefix and suffix (32 characters each) taken from the document.
- Rebase, for each pending proposal and each applied edit: an edit that ends at or before the proposal start shifts it by the edit's length change; an edit that starts at or after the proposal end leaves it; any shared character marks it stale. So an insert at the proposal start shifts it, and an insert at its end leaves it. After every write, prefix and suffix are re-copied from the new text for all pending proposals.
- Accept works only on a pending proposal; reject works on pending or stale. Anything else is 409.
- The search index updates only after commit. The index records which version it has indexed for each document, and applies a chunk update only when that matches the version the edit was computed from. Otherwise, or on any error, it logs and re-indexes the whole document from the committed text. Index updates are serialized with a lock.

**API**

- Document ids are UUIDs. ETags are quoted: `"<id>-<version>"`.
- Status codes: invalid payload 422, unresolvable or ambiguous target 422, overlapping changes 422, missing document or proposal 404, proposal in the wrong status 409, stale `If-Match` 412, missing `If-Match` 428, unexpected errors 500. All use the error format in section 4.
- `POST /documents/{id}/ai-redlines` returns 200 with the suggestions that anchored and the ones that were dropped, each with a reason code, plus the version and `ETag` they were computed against.
- Request ids are set by middleware in a context variable and included in every log line.

## 6. Folder structure

The backend packages map one-to-one to the architecture components. Each pure package (`editing`, `search`) has no imports from `storage`, `api`, or `services`.

```
redline/
├── README.md                          # setup, usage, performance numbers, API design rationale
├── Makefile                           # one-word commands: install, dev, test, bench, seed
├── .env.example                       # ANTHROPIC_API_KEY, DATABASE_URL, TEST_DATABASE_URL, LOG_LEVEL
├── .gitignore
├── docker-compose.yml                 # local Postgres for reviewers, on host port 5433
├── docker/postgres/init/              # creates the redline_test database on first start
├── docs/
│   ├── infra.md                       # Part II: production architecture and trade-offs
│   ├── assessment-prompt.md           # the Sandstone prompt, gitignored because it is confidential
│   └── plans/
│       └── build-plan.md              # this plan; phase plans sit beside it
├── sample_data/
│   ├── contracts/                     # realistic seed contracts (MSA, NDA, SaaS agreement)
│   └── playbook.json                  # sample legal playbook used by AI redlines
├── samples/
│   └── curl_requests.sh               # runnable curl walkthrough of every endpoint
├── backend/
│   ├── pyproject.toml                 # dependencies pinned with ~=, Ruff and pytest config
│   ├── src/redline/
│   │   ├── main.py                    # builds the FastAPI app, registers routes and error handlers, rebuilds the index on startup
│   │   ├── config.py                  # settings read from the environment
│   │   ├── logging_setup.py           # log format with request ids
│   │   ├── editing/                   # pure redline engine: no I/O
│   │   │   ├── models.py              # targets, Change, ResolvedChange, AppliedEdit
│   │   │   ├── errors.py              # InvalidTargetError, RangeOutOfBoundsError, TargetNotFoundError, AmbiguousTargetError, OverlappingChangesError
│   │   │   ├── anchors.py             # resolves each target type to an exact range
│   │   │   ├── apply.py               # validates a batch and rebuilds the text in one pass
│   │   │   └── rebase.py              # moves pending proposal ranges through applied edits, marks overlaps stale
│   │   ├── search/                    # pure search engine: no I/O
│   │   │   ├── models.py              # Token, IndexedChunk, SearchQuery, SearchScope, SearchHit, Snippet
│   │   │   ├── errors.py              # EmptyQueryError, DocumentNotIndexedError
│   │   │   ├── tokenizer.py           # word tokens with character offsets
│   │   │   ├── chunker.py             # splits text into paragraph chunks
│   │   │   ├── query_parser.py        # splits a query into terms and quoted phrases
│   │   │   ├── index.py               # positional inverted index with incremental chunk updates
│   │   │   ├── ranking.py             # BM25 scoring
│   │   │   ├── snippets.py            # context windows with highlight offsets
│   │   │   ├── query_runner.py        # candidates, phrase check, scoring, paging
│   │   │   └── retrieval.py           # ranks paragraph chunks for AI redlines (any term matches)
│   │   ├── ai/
│   │   │   ├── models.py              # PlaybookPosition, RedlineSuggestion, AnchoredSuggestion, DroppedSuggestion
│   │   │   ├── errors.py              # AiNotConfiguredError, ModelUnavailableError, ModelResponseError
│   │   │   ├── model_client.py        # RedlineModelClient protocol, the Anthropic client, and the unconfigured client
│   │   │   ├── prompts.py             # system prompt, user prompt, and the JSON schema for suggestions
│   │   │   ├── playbook.py            # loads the playbook file
│   │   │   └── anchoring.py           # anchors suggestions through the engine, drops the ones that don't resolve
│   │   ├── storage/
│   │   │   ├── schema.sql             # tables and indexes
│   │   │   ├── models.py              # typed rows: StoredDocument, DocumentSummary, DocumentVersion, ...
│   │   │   ├── errors.py              # DocumentNotFoundError, DocumentVersionNotFoundError
│   │   │   ├── database.py            # connection pool and schema setup
│   │   │   └── document_repository.py # documents and versions
│   │   ├── services/                  # orchestrates writes across engines and storage, one file per use case
│   │   │   ├── errors.py              # StaleVersionError
│   │   │   ├── document_service.py    # create a document, apply changes
│   │   │   ├── search_service.py      # owns the live index, keeps it in sync with writes
│   │   │   └── ai_redline_service.py  # picks the text to send, calls the model, anchors the suggestions
│   │   └── api/
│   │       ├── schemas.py             # request and response dataclasses
│   │       ├── etags.py               # builds and checks ETag / If-Match
│   │       ├── error_handlers.py      # maps errors to { error, code, error_type } responses
│   │       ├── dependencies.py        # shared FastAPI dependencies (database connection)
│   │       └── routes/
│   │           ├── health.py          # /health
│   │           ├── documents.py       # /documents, /documents/{id}, versions
│   │           ├── search.py          # /search and /documents/{id}/search
│   │           └── ai_redlines.py     # /documents/{id}/ai-redlines
│   ├── tests/
│   │   ├── conftest.py                # shared fixtures: test database rolled back per test, test client, fake model client
│   │   ├── fixtures/                  # small contract texts used across tests
│   │   ├── editing/                   # anchors, apply, rebase
│   │   ├── storage/                   # repositories against the test database
│   │   ├── services/                  # write paths, including the lost-race case
│   │   ├── search/                    # tokenizer, chunker, query parser, index, ranking, snippets
│   │   ├── ai/                        # anchoring, prompts, parsing, and the service with a fake model client
│   │   ├── api/                       # endpoint tests through the FastAPI test client
│   │   └── large_documents/           # 10MB edit and search correctness
│   └── scripts/
│       ├── seed.py                    # loads sample_data/contracts into the database
│       └── benchmark.py               # engine and index vs naive scan, using tests/fixtures/large_contract.py; prints a table for the README
└── frontend/
    ├── package.json
    ├── vite.config.ts                 # dev proxy to the backend
    ├── tsconfig.json
    ├── index.html
    └── src/
        ├── main.tsx                   # mounts the app with the query client
        ├── app.tsx                    # three-pane layout
        ├── api/
        │   ├── client.ts              # fetch wrapper: ETag handling, error parsing
        │   └── types.ts               # TypeScript types matching the API schemas
        ├── features/
        │   ├── documents/             # document list and document loading
        │   ├── redline/               # document view with inline redlines, changes panel, accept/reject
        │   ├── search/                # search bar, results, jump to match
        │   └── ai_redlines/           # instruction box, playbook toggle, suggestion review
        ├── components/                # shared UI pieces (buttons, panels, badges)
        ├── hooks/
        │   └── use_keyboard_shortcuts.ts  # review shortcuts
        └── styles/
            ├── tokens.css             # colors, type, spacing, redline colors
            └── global.css
```

## 7. Phases

Phases 1 to 3 plus the README are a complete baseline submission. Everything after that is a layer on top. If time runs out, stop at a phase boundary and list the rest as next steps. Phases 4 to 6 replaced the original proposals, AI, UI, and polish phases at the 3-hour mark (see the scope change in section 2). The search mode toggle ("Exact" vs "Natural language", reusing `search/retrieval.py`) is a UI extra if time allows.

| # | Phase | Delivers | Depends on | Done when |
|---|---|---|---|---|
| 1 | Editing engine | `editing` package: all three target types, atomic batch apply, overlap rejection, `AppliedEdit` output, rebase. Project tooling (`pyproject.toml`, Ruff, pytest, Makefile). | Nothing | `make test` passes, including a 10MB document with 1,000 changes applied correctly. |
| 2 | Storage and document API | Postgres schema, `docker-compose.yml`, repositories, document service. Endpoints: create, list, get (with ETag), `PATCH` apply (with `If-Match`), list and get versions. Error handlers, request ids, seed script, curl samples. README: setup, usage, and API design rationale. | 1 | `make dev` runs against Postgres; `samples/curl_requests.sh` creates, edits, and reads a document; a stale `If-Match` returns 412, including when two writes race; API tests pass. |
| 3 | Search | `search` package and search service. Index rebuilt on startup; the write path now re-indexes changed chunks after commit. `GET /search` (with optional `document_ids`) and `GET /documents/{id}/search`, with paging. Benchmark script, with its numbers added to the README. | 2 | Phrase and multi-word queries return ranked snippets; editing a document updates results immediately; the benchmark prints indexed vs naive timings on 10MB. |
| 4 | Search fixes and AI redline suggestions | Phrase search and benchmark fixes from the Phase 3 review. `ai` package, playbook, `search/retrieval.py` for large documents, and `POST /documents/{id}/ai-redlines` returning anchored and dropped suggestions. Unused proposal and compare scaffolds removed. | 3 | The rare-phrase benchmark row beats the scan; the common-phrase row is reported and explained. With a real key, "make the indemnification mutual" returns anchored suggestions with rationales, and applying them as one `PATCH` of range targets with the returned `ETag` works. Tests pass offline with the fake client. |
| 5 | UI | React app built and designed in one phase, to the approved "modern editorial" direction (warm off-white and charcoal-ink themes with a toggle, Newsreader document text, Instrument Serif headings and wordmark, Instrument Sans interface): document list, document view with suggestions as inline redlines, changes panel with accept and reject, accept all, AI instruction box, search with jump to match, keyboard review. | 2 to 4 | A reviewer can open a contract, ask for a playbook review, step through the suggestions from the keyboard, accept some, and search the result, in a UI that looks like a product. |
| 6 | Docs and Part II | README refreshed (final benchmark numbers, AI and UI sections, what was built within the time box), `docs/infra.md`. | All | A fresh clone runs from the README alone. |

## 8. Risks and open questions

- **Time box.** The prompt says 3 to 4 hours, and this plan is larger. Phases 1 to 3 plus the README are the honest core; later phases are stretch work. Decide at each boundary whether to continue, and say in the README what was built after the time box, if anything. Find out: track time per phase.
- **FastAPI with dataclass unions.** The change target is a union of three dataclasses. FastAPI validates dataclasses through Pydantic, but a discriminated union of plain dataclasses needs checking. Find out: spike it at the start of phase 2. The fallback is to make only the three target request types Pydantic models, which support discriminated unions natively, as a stated exception to the dataclass rule.
- **Python speed on 10MB.** Tokenizing 10MB in pure Python may take around a second. The startup rebuild is fine; per-edit cost is avoided by chunked re-indexing. Find out: the phase 3 benchmark.
- **LLM anchoring failures.** The model may quote text that is not exactly in the document. Find out: in phase 4, count anchored and dropped suggestions on the sample contracts; tighten the prompt to require exact quotes if many drop.
- **Reviewer setup.** Postgres adds a step that SQLite would not. Find out: run the README from a fresh clone with only Docker installed.
- **Full text per version.** Fine for the demo; it would grow fast in production. Covered in Part II.
- **Part III extension.** The live session may ask for a new redline rule or a search feature. The pure, typed engine packages are designed so either is a small, local change.

## 9. Engineering conventions

- All code follows the `code-guidelines` skill: dataclasses for structured data, enums instead of literals, docstrings on every function, absolute imports, no logic in `__init__.py`, logging with request ids at entry, exit, and error points, and no inline styles in the frontend.
- The process never crashes on a bad request: route handlers catch errors and return `{ error, code, error_type }`.
- Pure packages (`editing`, `search`) do no I/O and do not import from `storage`, `services`, or `api`.
- Class docstrings keep the blank line Ruff's formatter adds (Ruff has no setting for it); no `# fmt: off` blocks.
- Tests follow set up, act, assert, and check error types and codes rather than message strings.
- Reviews use `code-guidelines-review`.
- Each phase gets its own plan in `docs/plans/` (for example `phase-1-editing-engine.md`). When a phase plan changes the architecture, structure, or phases, this file is updated in the same pass.
