# Phase 2: Storage and Document API

**Project:** Redline (see `docs/plans/build-plan.md`; section 5's "Behavior rules" apply)
**Audience:** the coding agent building this phase

Read and follow the `code-guidelines` skill before writing any code. If this plan and the guidelines disagree, the guidelines win: follow them and tell the user what differed.

Code snippets in this plan are hints, not ground truth. Check the current docs for FastAPI, Pydantic, psycopg 3, psycopg_pool, and Uvicorn before using them. During checkpoints 4 to 6 you will start the dev server; stop it when the checkpoint is reported.

## Goal

Put the Phase 1 engine behind a JSON API backed by Postgres. Documents are created, listed, and read, and they are edited with `PATCH /documents/{id}`. Edits are atomic batches of changes, each targeted by range, occurrence, or context. Every write creates a new version. Reads return an `ETag`, and writes require `If-Match` and save with a compare-and-swap, so a stale write gets a 412. Every error is JSON `{ error, code, error_type }`. Every log line carries a request id. The phase also delivers the Docker Postgres setup, three original sample contracts with a seed script, a curl walkthrough, and the first real README.

**Out of scope:** search and re-indexing (phase 3); proposals, rebasing on writes, and compare (phase 4); the AI and the frontend. Phase 2 does not call `rebase_span` and has no placeholder hooks for later phases.

## Files

```
redline/
├── Makefile                                   # section 11
├── .env.example                               # section 1
├── docker-compose.yml                         # section 1
├── docker/postgres/init/
│   └── create_test_database.sql               # section 1 (new)
├── README.md                                  # section 13
├── samples/curl_requests.sh                   # section 12
├── sample_data/contracts/
│   ├── master_services_agreement.txt          # section 12 (new)
│   ├── mutual_nda.txt                         # section 12 (new)
│   └── saas_subscription_agreement.txt        # section 12 (new)
└── backend/
    ├── pyproject.toml                         # section 1
    ├── src/redline/
    │   ├── editing/errors.py                  # section 0 (renames)
    │   ├── config.py                          # section 2
    │   ├── logging_setup.py                   # section 2
    │   ├── main.py                            # section 10
    │   ├── storage/
    │   │   ├── schema.sql                     # section 3
    │   │   ├── models.py                      # section 4 (new)
    │   │   ├── errors.py                      # section 4 (new)
    │   │   ├── database.py                    # section 5
    │   │   └── document_repository.py         # section 5
    │   ├── services/
    │   │   ├── errors.py                      # section 6 (new)
    │   │   └── document_service.py            # section 6
    │   └── api/
    │       ├── schemas.py                     # section 7
    │       ├── etags.py                       # section 8
    │       ├── error_handlers.py              # section 9
    │       ├── dependencies.py                # section 10
    │       └── routes/
│           ├── documents.py               # section 10
│           └── health.py                  # section 10 (new)
    ├── scripts/seed.py                        # section 12
    └── tests/
        ├── conftest.py                        # section 14
        ├── editing/*.py                       # section 0 (renames only)
        ├── storage/
        │   ├── __init__.py                    # new, empty
        │   └── test_document_repository.py    # section 14 (new)
        ├── services/
        │   ├── __init__.py                    # new, empty
        │   └── test_document_service.py       # section 14 (new)
        ├── api/
        │   ├── test_etags.py                  # section 14 (new)
        │   ├── test_documents_api.py          # section 14 (new)
        │   └── test_request_ids.py            # section 14 (new)
        └── large_documents/
            └── test_large_document_api.py     # section 14 (new)
```

## 0. Rename the engine exceptions

Phase 1 silenced Ruff's N818 for `editing/errors.py`. PEP 8 asks for an `Error` suffix, and this phase starts mapping these classes into the API, so rename them now and remove the per-file ignore from `pyproject.toml`:

| Old | New |
|---|---|
| `InvalidTarget` | `InvalidTargetError` |
| `RangeOutOfBounds` | `RangeOutOfBoundsError` |
| `TargetNotFound` | `TargetNotFoundError` |
| `AmbiguousTarget` | `AmbiguousTargetError` |
| `OverlappingChanges` | `OverlappingChangesError` |

`InvalidTargetReason` and `EditingError` keep their names. Update every import and test, and rename tests whose names mention the old classes (`..._raises_target_not_found` becomes `..._raises_target_not_found_error`). All new exception classes in this phase end in `Error`.

Remove the `# fmt: off` / `# fmt: on` blocks in `editing/models.py`, `editing/errors.py`, and `tests/large_documents/test_large_edits.py`, and run `make format`. The blank line Ruff's formatter puts after a class docstring stays: Ruff has no setting for it, and switching the formatter off for whole files is worse than that one blank line. Function docstrings still sit directly on the first line of code, as the guidelines ask.

## 1. Infrastructure

### `docker-compose.yml`

One `postgres` service:
- Image: `postgres:18` (18.6 is the current stable release).
- Environment: `POSTGRES_USER=redline`, `POSTGRES_PASSWORD=redline`, `POSTGRES_DB=redline`.
- Port `5433:5432`. The host side is 5433 so it doesn't clash with a Postgres already running on 5432 (the user has one).
- A named volume for data.
- `./docker/postgres/init` mounted at `/docker-entrypoint-initdb.d`.
- Healthcheck: `pg_isready -h 127.0.0.1 -U redline -d redline`. Checking over TCP matters: a socket-only check reports healthy during the image's first-boot init, before `redline_test` exists.

### `docker/postgres/init/create_test_database.sql`

`CREATE DATABASE redline_test;` This runs once, when the volume is first created.

### `.env.example`

```
# Anthropic API key, needed only for AI redlines
ANTHROPIC_API_KEY=
# Postgres connection strings (port 5433 matches docker-compose.yml)
DATABASE_URL=postgresql://redline:redline@localhost:5433/redline
TEST_DATABASE_URL=postgresql://redline:redline@localhost:5433/redline_test
# Logging level: DEBUG, INFO, WARNING, ERROR
LOG_LEVEL=INFO
```

### `backend/pyproject.toml`

Runtime dependencies: `fastapi~=0.162.2`, `uvicorn[standard]~=0.54.0`, `psycopg[binary]~=3.3.8`, `psycopg-pool~=3.3.3`. Dev group: add `httpx~=0.28.1` (the FastAPI test client needs it). All have Python 3.14 macOS arm64 wheels. Commit `uv.lock`.

## 2. Config and logging

### `config.py`

```python
DATABASE_URL_VARIABLE = "DATABASE_URL"
LOG_LEVEL_VARIABLE = "LOG_LEVEL"

@dataclass(frozen=True)
class Settings:
    """Settings the server needs to start."""
    database_url: str
    log_level: str

def load_settings() -> Settings:
    """Read settings from the environment, failing with a clear message when one is missing."""
```

Check for each variable with `in os.environ` and read with `os.environ[...]`, never `.get()`. A missing variable raises `RuntimeError` naming the variable (never its value). This runs at startup, before any request, so failing fast is right here.

### `logging_setup.py`

```python
NO_REQUEST_ID = "-"
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s [request %(request_id)s] %(message)s"
request_id_context: ContextVar[str] = ContextVar("request_id", default=NO_REQUEST_ID)
```

- `class RequestIdFilter(logging.Filter)`: `filter(self, record)` sets `record.request_id` from `request_id_context` and returns `True`.
- `configure_logging(log_level: str) -> None`: one stream handler on the root logger with the filter and the format.

Every log line, including the Phase 1 engine's, now carries the request id without the engine knowing about requests.

## 3. `storage/schema.sql`

Applied on every startup, so every statement is idempotent.

```sql
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY,
    title TEXT NOT NULL,
    current_version INTEGER NOT NULL CHECK (current_version >= 1),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS document_versions (
    document_id UUID NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
    version INTEGER NOT NULL CHECK (version >= 1),
    text TEXT NOT NULL,
    author TEXT NOT NULL,
    summary TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (document_id, version)
);

CREATE INDEX IF NOT EXISTS documents_updated_at_index ON documents (updated_at DESC);
```

The primary key on `(document_id, version)` is the uniqueness guard from the behavior rules. There's no foreign key from `documents.current_version` to `document_versions`, because the compare-and-swap bumps the version before that version's row is inserted, inside the same transaction.

## 4. Storage types and errors

### `storage/models.py`

All `@dataclass(frozen=True)`. Field names match the SQL column aliases, so `psycopg.rows.class_row` builds them directly.

| Class | Fields |
|---|---|
| `StoredDocument` | `id: UUID`, `title: str`, `version: int`, `text: str`, `created_at: datetime`, `updated_at: datetime` |
| `DocumentSummary` | `id: UUID`, `title: str`, `version: int`, `character_count: int`, `updated_at: datetime` |
| `DocumentPage` | `documents: list[DocumentSummary]`, `total_count: int` |
| `DocumentVersion` | `document_id: UUID`, `version: int`, `text: str`, `author: str`, `summary: str`, `created_at: datetime` |
| `VersionSummary` | `version: int`, `author: str`, `summary: str`, `character_count: int`, `created_at: datetime` |

### `storage/errors.py`

- `StorageError(Exception)`: base class.
- `DocumentNotFoundError(document_id: UUID)`
- `DocumentVersionNotFoundError(document_id: UUID, version: int)`

## 5. Database access

### `database.py`

```python
SCHEMA_PATH = Path(__file__).parent / "schema.sql"
POOL_MINIMUM_SIZE = 1
POOL_MAXIMUM_SIZE = 10
```

- `open_connection_pool(database_url: str) -> ConnectionPool`: opens a `psycopg_pool.ConnectionPool` with `kwargs={"autocommit": True}` and `open=True`, then waits until it's ready. Check the current psycopg_pool docs for `open` and `wait`.
- `apply_schema(connection: Connection) -> None`: runs `schema.sql`.

**Transactions:** connections are in autocommit mode, and every write uses an explicit `with connection.transaction():` block (psycopg's recommended style). This also makes tests simple: a test wraps everything in an outer transaction that is always rolled back, and the inner `transaction()` blocks become savepoints (section 14).

### `document_repository.py`

SQL lives in `UPPER_CASE` string constants at the top of the file. Use parameters (`%s`), never string formatting, and `class_row` for typed rows. Each function does one statement, takes the connection as its first argument, and does not open transactions. The service owns transactions.

| Function | SQL / behavior |
|---|---|
| `insert_document(connection, document_id: UUID, title: str) -> None` | insert with `current_version = 1` |
| `insert_document_version(connection, document_id: UUID, version: int, text: str, author: str, summary: str) -> None` | insert one version row |
| `advance_document_version(connection, document_id: UUID, expected_version: int) -> bool` | `UPDATE documents SET current_version = current_version + 1, updated_at = now() WHERE id = %s AND current_version = %s`; returns `cursor.rowcount == 1` |
| `get_document(connection, document_id: UUID) -> StoredDocument` | join `documents` with its current version row; raises `DocumentNotFoundError` when there's no row |
| `list_documents(connection, limit: int, offset: int) -> DocumentPage` | summaries ordered by `updated_at DESC, id`, with `char_length(text) AS character_count`, and the total from a separate `SELECT count(*) FROM documents`. Not `count(*) OVER ()`, which has no row to sit on when the page is past the end, so the total would read as 0. |
| `list_document_versions(connection, document_id: UUID) -> list[VersionSummary]` | ordered by `version DESC`; an empty list means no such document (every document has version 1), so raise `DocumentNotFoundError` |
| `get_document_version(connection, document_id: UUID, version: int) -> DocumentVersion` | raises `DocumentVersionNotFoundError` when there's no row |
| `get_document_updated_at(connection, document_id: UUID) -> datetime` | `SELECT updated_at FROM documents WHERE id = %s` |
| `get_current_version(connection, document_id: UUID) -> int` | `SELECT current_version FROM documents WHERE id = %s`; raises `DocumentNotFoundError` when there's no row |

## 6. Services

### `services/errors.py`

- `ServiceError(Exception)`: base class.
- `StaleVersionError(document_id: UUID, expected_version: int, current_version: int)`: the client's `If-Match` names a version that's no longer current.

### `document_service.py`

```python
CREATED_DOCUMENT_SUMMARY = "Created document"
APPLIED_CHANGES_SUMMARY = "Applied {change_count} changes"
FIRST_VERSION = 1

@dataclass(frozen=True)
class AppliedDocumentChanges:
    """A document after a batch of changes, and where each edit landed."""
    document: StoredDocument
    applied_edits: list[AppliedEdit]
```

| Function | One job |
|---|---|
| `create_document(connection, title: str, text: str, author: str) -> StoredDocument` | Generate the id with `uuid.uuid7()` (new in Python 3.14, time-ordered so inserts stay sequential in the index), insert the document and version 1 in one transaction, and return the stored document. |
| `apply_document_changes(connection, document_id: UUID, expected_version: int, changes: list[Change], author: str) -> AppliedDocumentChanges` | The write path below. |

`apply_document_changes`, step by step:

1. `get_document`. If `document.version != expected_version`, raise `StaleVersionError`. That fails fast before any work.
2. `apply_changes(document.text, changes)`, **outside** any transaction. Engine errors propagate unchanged.
3. `with connection.transaction():`
   1. `advance_document_version(...)`. If it returns `False`, another write got in between step 1 and now: read `get_current_version` (which raises `DocumentNotFoundError` if the row is gone), log a warning with both versions, and raise `StaleVersionError` with both. Raising inside the block rolls the transaction back. `advance_document_version` still returns `bool`.
   2. `insert_document_version(..., version=expected_version + 1, ...)` with the summary built from `APPLIED_CHANGES_SUMMARY`.
4. Read the new `updated_at` with `get_document_updated_at` (below), then return `AppliedDocumentChanges`. Build the `StoredDocument` from what's already in hand (the new version and the new text) rather than re-reading 10MB from the database.

Add `get_document_updated_at(connection, document_id: UUID) -> datetime` to the repository (`SELECT updated_at FROM documents WHERE id = %s`). `advance_document_version` keeps returning `bool` instead of `RETURNING updated_at` into a `datetime | None`, because the guidelines prefer avoiding optional values.

Log entry (document id, expected version, change count, author) and exit (new version, new length) for both public functions. Log the 412 path at warning with both versions.

**Reads skip the service layer.** `get_document`, `list_documents`, and the version reads are single repository calls, so the routes call the repository directly. A service function that only forwards a call is a thin wrapper, which the guidelines forbid. Writes go through services because they have real orchestration.

## 7. `api/schemas.py`

Request and response types are standard `@dataclass`es, not Pydantic models. FastAPI validates dataclasses through Pydantic, and Pydantic's `Field` is used only inside `Annotated[...]` for a discriminator or a length constraint.

### Requests

```python
class ChangeTargetType(StrEnum):
    """How a change points at text."""
    RANGE = "range"
    OCCURRENCE = "occurrence"
    CONTEXT = "context"

@dataclass
class RangeTargetRequest:
    type: Literal[ChangeTargetType.RANGE]
    start: int
    end: int

@dataclass
class OccurrenceTargetRequest:
    type: Literal[ChangeTargetType.OCCURRENCE]
    text: str
    occurrence: int

@dataclass
class ContextTargetRequest:
    type: Literal[ChangeTargetType.CONTEXT]
    text: str
    prefix: str
    suffix: str

TargetRequest = Annotated[
    RangeTargetRequest | OccurrenceTargetRequest | ContextTargetRequest,
    Field(discriminator="type"),
]

@dataclass
class ChangeRequest:
    target: TargetRequest
    replacement: str

@dataclass
class ApplyChangesRequest:
    author: Annotated[str, Field(min_length=1)]
    changes: Annotated[list[ChangeRequest], Field(min_length=1)]

@dataclass
class CreateDocumentRequest:
    title: Annotated[str, Field(min_length=1)]
    text: str
    author: Annotated[str, Field(min_length=1)]
```

Wire format of one change:

```json
{ "target": { "type": "occurrence", "text": "Seller", "occurrence": 2 }, "replacement": "Vendor" }
```

There's no `operation` field. Every change is "replace this span": an empty `replacement` deletes, and a zero-width target inserts. The README explains this.

`to_change(request: ChangeRequest) -> Change` maps a request onto the engine types with a `match` on the target class. The `case _` fallback logs and raises `InvalidTargetError` with `UNKNOWN_TARGET_TYPE`. The `change_index` comes from the caller's `enumerate`. Don't validate offsets or occurrence numbers here: the engine is the one place those rules live, and its errors already map to 422.

### Responses

| Class | Fields |
|---|---|
| `DocumentResponse` | `id: UUID`, `title: str`, `version: int`, `text: str`, `created_at: datetime`, `updated_at: datetime` |
| `AppliedEditResponse` | `start: int`, `end: int`, `replacement_length: int` (offsets in the text before the batch) |
| `ApplyChangesResponse` | `document: DocumentResponse`, `applied_edits: list[AppliedEditResponse]` |
| `DocumentSummaryResponse` | `id`, `title`, `version`, `character_count`, `updated_at` |
| `DocumentListResponse` | `documents: list[DocumentSummaryResponse]`, `total_count: int`, `limit: int`, `offset: int` |
| `VersionSummaryResponse` | `version`, `author`, `summary`, `character_count`, `created_at` |
| `DocumentVersionResponse` | `document_id`, `version`, `text`, `author`, `summary`, `created_at` |
| `ErrorResponse` | `error: str`, `code: int`, `error_type: ErrorType` |

Mapping from storage types is done in the route with the constructor, field by field. Don't add helpers that only call a constructor.

**Checkpoint 2 settles the open risk:** whether FastAPI validates this discriminated union of plain dataclasses, with `Literal` enum members and `Field` constraints in `Annotated`, and returns a 422 for a wrong `type`. If it doesn't, **stop and tell the user**. The agreed fallback is to make only `RangeTargetRequest`, `OccurrenceTargetRequest`, and `ContextTargetRequest` Pydantic `BaseModel`s, which support discriminated unions natively, keeping every field required. Everything else stays a dataclass, and a comment on the three classes says why they're the exception.

## 8. `api/etags.py`

```python
ETAG_FORMAT = '"{document_id}-{version}"'
```

- `build_etag(document_id: UUID, version: int) -> str`
- `parse_if_match(if_match: str, document_id: UUID) -> int`: returns the version. Raises `PreconditionFailedError` when the value isn't exactly one quoted ETag in our format, or names another document. `*`, weak ETags (`W/"..."`), and lists are rejected with 412: we only ever issue strong, single ETags, so anything else can't match. Note that the document id itself contains hyphens; split on the **last** hyphen.

`PreconditionFailedError(if_match: str)` and `PreconditionRequiredError()` are defined in `etags.py`. They are API-level errors about headers.

## 9. `api/error_handlers.py`

```python
class ErrorType(StrEnum):
    VALIDATION_ERROR = "validation_error"
    INVALID_TARGET = "invalid_target"
    RANGE_OUT_OF_BOUNDS = "range_out_of_bounds"
    TARGET_NOT_FOUND = "target_not_found"
    AMBIGUOUS_TARGET = "ambiguous_target"
    OVERLAPPING_CHANGES = "overlapping_changes"
    DOCUMENT_NOT_FOUND = "document_not_found"
    VERSION_NOT_FOUND = "version_not_found"
    PRECONDITION_FAILED = "precondition_failed"
    PRECONDITION_REQUIRED = "precondition_required"
    HTTP_ERROR = "http_error"
    INTERNAL_ERROR = "internal_error"
```

`register_error_handlers(app: FastAPI) -> None` registers one handler per row. Each handler logs (warning for 4xx, `logger.exception` for 500) and returns `JSONResponse` built from `ErrorResponse`.

| Exception | Status | `error_type` | `error` |
|---|---|---|---|
| `RequestValidationError` | 422 | `validation_error` | a short summary built from the first validation error's location and message. Logs the location and error type only, never the submitted input, which may be contract text. |
| `InvalidTargetError` | 422 | `invalid_target` | the exception's message |
| `RangeOutOfBoundsError` | 422 | `range_out_of_bounds` | " |
| `TargetNotFoundError` | 422 | `target_not_found` | " |
| `AmbiguousTargetError` | 422 | `ambiguous_target` | " |
| `OverlappingChangesError` | 422 | `overlapping_changes` | " |
| `DocumentNotFoundError` | 404 | `document_not_found` | " |
| `DocumentVersionNotFoundError` | 404 | `version_not_found` | " |
| `StaleVersionError` | 412 | `precondition_failed` | " |
| `PreconditionFailedError` | 412 | `precondition_failed` | " |
| `PreconditionRequiredError` | 428 | `precondition_required` | " |
| `starlette.exceptions.HTTPException` (FastAPI's subclass included) | the exception's status, such as 404 for an unknown path or 405 for a wrong method | `http_error` | the standard reason phrase for that status (`http.HTTPStatus(code).phrase`) |
| `Exception` | 500 | `internal_error` | `"Internal server error"` (never the exception's text) |

Check in the Starlette docs how a handler for `Exception` behaves (it runs in the server-error middleware). The client must get the JSON body, and the server must keep running.

## 10. App, dependencies, routes

### `main.py`

- `create_app(settings: Settings) -> FastAPI`: configures logging, registers the lifespan, the request-id middleware, the error handlers, and the routes.
- **Lifespan:** opens the pool, applies the schema, stores the pool on `app.state.connection_pool`, and closes the pool on shutdown.
- **Request-id middleware:** a plain ASGI middleware class (`RequestIdMiddleware`, in `main.py`), not `@app.middleware("http")`. That decorator is Starlette's `BaseHTTPMiddleware`, which doesn't carry context variables reliably. Use the incoming `X-Request-ID` header when it is at most `MAXIMUM_REQUEST_ID_LENGTH = 64` characters and has no whitespace; otherwise generate `uuid.uuid4().hex`. Set `request_id_context`, call the app, and add `X-Request-ID` to the response headers. AnyIO copies the context into the thread pool, so sync (`def`) routes see the id. The `RequestIdFilter` goes on the root logger's handler, so `caplog` records get `request_id` too.
- `build_app() -> FastAPI`: `create_app(load_settings())`. Uvicorn runs it with `--factory`, so importing `main.py` in tests reads no environment variables.

### `dependencies.py`

`get_connection(request: Request) -> Iterator[Connection]`: yields a connection from `request.app.state.connection_pool.connection()`. Tests override this dependency (section 14).

### `routes/documents.py`

Routes are sync `def` functions (psycopg is used synchronously, and FastAPI runs sync routes in its thread pool). Each logs entry and exit with the document id. `DEFAULT_PAGE_LIMIT = 20` and `MAXIMUM_PAGE_LIMIT = 100` are constants. The `If-Match` header is declared as `Annotated[str | None, Header()] = None`. It's optional on purpose: a missing header must become 428, not FastAPI's 422. Raise `PreconditionRequiredError` when it's `None`.

| Method and path | Request | Success | Headers |
|---|---|---|---|
| `POST /documents` | `CreateDocumentRequest` | 201 `DocumentResponse` | `ETag`, `Location: /documents/{id}` |
| `GET /documents?limit=&offset=` | limit 1 to 100 (default 20), offset ≥ 0 (default 0) | 200 `DocumentListResponse` | |
| `GET /documents/{document_id}` | | 200 `DocumentResponse` | `ETag` |
| `PATCH /documents/{document_id}` | `ApplyChangesRequest`, `If-Match` required | 200 `ApplyChangesResponse` | new `ETag` |
| `GET /documents/{document_id}/versions` | | 200 `list[VersionSummaryResponse]` | |
| `GET /documents/{document_id}/versions/{version}` | | 200 `DocumentVersionResponse` | |
| `GET /health` | | 200 `{"status": "ok"}` after `SELECT 1` | |

`/health` goes in its own small router file, `routes/health.py` (new). `document_id` is a `UUID` path parameter, so a malformed id is a 422 `validation_error`.

## 11. `Makefile`

`test`, `dev`, and `seed` load `.env`. `install`, `lint`, and `format` stay runnable before `.env` exists. The test database URL is read inside the database fixtures, so the Phase 1 tests still run without it. Targets:

| Target | Runs |
|---|---|
| `db-up` | `docker compose up -d --wait` |
| `db-down` | `docker compose down` |
| `dev` | `cd backend && uv run --env-file ../.env uvicorn redline.main:build_app --factory --reload` |
| `seed` | `cd backend && uv run --env-file ../.env python scripts/seed.py` |
| `test` | `cd backend && uv run --env-file ../.env pytest` |

## 12. Sample data, seed, and curl walkthrough

### Contracts

Write three original contracts as plain text, about 1,500 to 3,000 words each. Write them fresh; don't copy real agreements. Use numbered sections separated by blank lines (the phase 3 chunker splits on blank lines). Together they must include:
- defined terms in quotes with possessives in use (`"Company"` and "the Company's obligations");
- a **one-sided indemnification** clause (the phase 5 demo makes it mutual);
- an **uncapped or very high limitation of liability**;
- governing law, termination for convenience, assignment with change of control, and confidentiality;
- the same phrase repeated in several places, such as "the Customer shall", so context targets are needed.

Files: `master_services_agreement.txt`, `mutual_nda.txt`, `saas_subscription_agreement.txt`.

### `scripts/seed.py`

`main()` loads settings, opens a pool, applies the schema, and creates one document per contract file (title: the file name without its extension, with underscores turned into spaces; author `"Seed"`) through `create_document`. If any documents already exist (`list_documents` with limit 1 has `total_count > 0`), it logs that it's skipping and exits. `main()` is the process boundary: catch `Exception`, log it, and exit non-zero.

### `samples/curl_requests.sh`

`set -euo pipefail`, `BASE_URL` defaulting to `http://localhost:8000`. Use `python3 -c` to pull fields out of JSON (no `jq` dependency), and print a heading per step. Steps:

1. Create a short contract and capture its id and `ETag`.
2. Get it and show the `ETag`.
3. Patch with an occurrence target.
4. Patch with a context target that picks one of two repeated phrases.
5. Patch a batch mixing a range delete, a zero-width insert, and a replacement.
6. Reuse the old `ETag` → 412.
7. Omit `If-Match` → 428.
8. Overlapping changes → 422 `overlapping_changes`.
9. Text not found → 422 `target_not_found`.
10. Unknown id → 404.
11. List versions, then get version 1.

## 13. `README.md`

Write the README now. Phase 3 adds search and benchmark numbers, and phase 8 refreshes it. Sections:

- **What it is:** two or three sentences.
- **Setup:** `cp .env.example .env`, `make db-up`, `make install`, `make seed`, `make dev`, and the API docs at `http://localhost:8000/docs`. Plus a short "using your own Postgres" note (create the role and both databases, then change the URLs).
- **Usage:** the curl examples for create, get, and the three target types, and a pointer to `samples/curl_requests.sh`.
- **API design:** one resource per noun; `PATCH` for edits because a request is a partial change described by our own JSON, not a full replacement (and not JSON Patch, whose paths address JSON fields, not text spans); three target types and why; no `operation` field; atomic batches; `ETag`/`If-Match` with compare-and-swap; the error format and a status code table; reads going straight to repositories.
- **Performance:** the Phase 1 design notes (linear rebuild, resolution cost, pre-batch offsets) and the 10MB test timings. Phase 3 adds a benchmark table.
- **Testing:** `make test`, and that database tests roll back.
- **Next steps:** the "deliberately left for later" list from the build plan.

## 14. Tests

### `tests/conftest.py`

- Read `TEST_DATABASE_URL` (fail clearly if missing). Never touch `DATABASE_URL` in tests.
- `test_settings` (session scope): `Settings(database_url=<test url>, log_level="WARNING")`.
- `schema_ready` (session scope): connects once and runs `apply_schema`.
- `connection` (function scope): an autocommit connection inside `with connection.transaction(force_rollback=True):` (check psycopg's `transaction` signature). The service's own `transaction()` blocks become savepoints inside it, so nothing a test writes survives the test.
- `client` (function scope): `TestClient(create_app(test_settings), raise_server_exceptions=False)` used as a context manager so the lifespan runs, with `app.dependency_overrides[get_connection]` yielding the `connection` fixture.

Tests assert on their own document ids, never on table totals. The exception is `total_count` checks, which compare before and after inside the same test.

### `tests/storage/test_document_repository.py`

- `test_inserted_document_reads_back_with_its_first_version`
- `test_get_missing_document_raises_document_not_found_error`
- `test_advance_document_version_succeeds_with_current_version`
- `test_advance_document_version_fails_with_stale_version` (advance once, then advance again with the same expected version: `False`)
- `test_duplicate_version_insert_is_rejected` (assert `psycopg.errors.UniqueViolation`)
- `test_list_document_versions_returns_newest_first`
- `test_list_versions_of_missing_document_raises_document_not_found_error`
- `test_get_missing_document_version_raises_document_version_not_found_error`
- `test_list_documents_pages_with_limit_and_offset`
- `test_list_documents_page_past_end_keeps_total_count`
- `test_get_current_version_of_missing_document_raises_document_not_found_error`

### `tests/services/test_document_service.py`

- `test_create_document_stores_version_one`
- `test_apply_changes_creates_next_version_with_author_and_summary`
- `test_apply_changes_with_stale_expected_version_raises_stale_version_error` (and no version 2 row exists)
- `test_lost_race_raises_stale_version_error_and_saves_nothing`: create a document and keep its version 1 `StoredDocument`. Simulate a second writer that commits between step 1 and step 3: call `advance_document_version` and `insert_document_version` directly to make version 2. Then monkeypatch `redline.services.document_service.get_document` to return the saved version 1 snapshot, so step 1's check passes, and call `apply_document_changes` with expected version 1. Assert `StaleVersionError`, that the current version is still 2, and that no version 3 row exists. This is the test that proves the compare-and-swap, not just the early check.
- `test_engine_error_leaves_document_unchanged` (a `TargetNotFoundError` batch: version stays 1)

### `tests/api/test_etags.py`

- `test_build_etag_quotes_document_id_and_version`
- `test_parse_if_match_returns_version_for_matching_document`
- `test_parse_if_match_for_other_document_raises_precondition_failed_error`
- `test_parse_if_match_without_quotes_raises_precondition_failed_error`
- `test_parse_if_match_wildcard_raises_precondition_failed_error`
- `test_parse_if_match_weak_etag_raises_precondition_failed_error`
- `test_parse_if_match_list_raises_precondition_failed_error`

### `tests/api/test_documents_api.py`

Create documents through the API inside each test. Assert status codes, `error_type`, `code`, and fields; never `error` strings.

- `test_create_document_returns_201_with_etag_and_location`
- `test_create_document_with_empty_title_returns_validation_error`
- `test_get_document_returns_text_and_etag`
- `test_get_missing_document_returns_404_document_not_found`
- `test_get_document_with_malformed_id_returns_validation_error`
- `test_list_documents_includes_created_document`
- `test_list_documents_with_limit_above_maximum_returns_validation_error`
- `test_patch_with_range_target_returns_updated_text_and_new_etag`
- `test_patch_with_occurrence_target_replaces_that_occurrence`
- `test_patch_with_context_target_replaces_matching_phrase`
- `test_patch_batch_reports_applied_edits_in_pre_batch_offsets`
- `test_patch_without_if_match_returns_428`
- `test_patch_with_stale_if_match_returns_412`
- `test_patch_with_other_documents_etag_returns_412`
- `test_second_patch_with_same_if_match_returns_412`
- `test_patch_with_overlapping_changes_returns_422_overlapping_changes`
- `test_patch_with_missing_text_returns_422_target_not_found`
- `test_patch_with_ambiguous_context_returns_422_ambiguous_target`
- `test_patch_with_invalid_range_returns_422_invalid_target`
- `test_patch_with_range_past_end_returns_422_range_out_of_bounds`
- `test_patch_with_empty_changes_returns_validation_error`
- `test_patch_with_unknown_target_type_returns_validation_error`
- `test_patch_missing_document_returns_404`
- `test_list_versions_after_patch_shows_both_versions`
- `test_get_version_one_after_patch_returns_original_text`
- `test_get_missing_version_returns_404_version_not_found`
- `test_unexpected_error_returns_500_internal_error` (override a dependency to raise `RuntimeError`; assert the JSON body and that the next request still succeeds)
- `test_health_returns_ok`
- `test_unknown_path_returns_404_http_error`
- `test_wrong_method_returns_405_http_error`

### `tests/api/test_request_ids.py`

- `test_response_echoes_given_request_id`
- `test_response_gets_generated_request_id_when_none_given`
- `test_request_id_with_whitespace_is_replaced`
- `test_request_id_over_maximum_length_is_replaced`
- `test_request_id_is_attached_to_log_records` (use `caplog`; the record logged during the request has that `request_id`)

### `tests/large_documents/test_large_document_api.py`

- `test_large_document_round_trip_through_api`: create a 10MB document (from `build_large_contract`) through `POST /documents`, `PATCH` it with 200 occurrence-targeted changes on unique section labels written as `Section {number}.` (with the period, so section 1 can't match section 10), and check the response text matches applying the same changes with `apply_changes` directly, and that version 2 reads back the same text.

## 15. Design notes (for the README)

- **Compare-and-swap, not a held lock.** The edit is computed with no transaction open, then one `UPDATE ... WHERE current_version = v` both checks and claims the next version. The first writer wins and the second gets 412, with no row lock held while a 10MB document is rebuilt.
- **Fail fast, then re-check.** The service compares versions before computing, to skip wasted work, and the compare-and-swap re-checks at commit, because the first check alone can race.
- **Strict `If-Match`.** We only issue strong, single ETags, so `*`, weak tags, and lists can never be a correct claim about the current version, and they get 412.
- **Full text per version.** Simple and exact for a prototype. In production, versions would be stored as deltas or content-addressed chunks (Part II).
- **UUIDv7 ids.** They sort by creation time, which keeps primary key inserts sequential.
- **Sync routes.** psycopg is used synchronously and FastAPI runs sync routes in a thread pool, which avoids mixing async and blocking code. With high concurrency this would move to psycopg's async API.

## Checkpoints ✅

Stop at each checkpoint and report before going on.

1. **Renames and infra.** Exceptions renamed, `make lint` and `make test` (Phase 1 tests) pass. `make db-up` is healthy. Report `docker compose ps`, and `psql postgresql://redline:redline@localhost:5433/redline -c '\l'` showing both `redline` and `redline_test`.
2. **Schema check on the union.** Before writing routes, a scratch test (deleted afterwards) or the first API tests show FastAPI accepting each target type, and rejecting a wrong `type` with a 422 that goes through our handler. Report what worked, and whether the fallback in section 7 was needed.
3. **Storage and service.** `uv run --env-file ../.env pytest tests/storage tests/services -v`. Report the list, then run `psql ... redline_test -c 'SELECT count(*) FROM documents'` and report it, to show the tests left nothing behind.
4. **API.** `make test` passes. Start `make dev` and report the startup log lines (with request id `-`) and one request's log lines (with its id).
5. **Seed and curl.** `make seed`, then `bash samples/curl_requests.sh`. Report the output, trimmed of contract text, showing every step's status code.
6. **Final.** `make lint` and `make test` totals. Report the README's section headings.

## Definition of done

- [ ] Engine exceptions end in `Error`, the N818 ignore is gone, and there are no `# fmt: off` blocks.
- [ ] `docker compose` starts Postgres on 5433 with `redline` and `redline_test`.
- [ ] `make db-up`, `make dev`, `make seed`, `make test`, and `make lint` work from the repo root.
- [ ] Every endpoint in section 10 works, with `ETag` and `If-Match` as specified, and every error is `{ error, code, error_type }` with the section 9 status.
- [ ] Writes follow section 6: version check, engine outside the transaction, compare-and-swap first inside it.
- [ ] Log lines carry request ids, and no log line contains document text or connection strings.
- [ ] Every test named in section 14 exists and passes, and tests leave the test database empty.
- [ ] Three original contracts, the seed script, and `samples/curl_requests.sh` work end to end.
- [ ] The README has the section 13 sections.
- [ ] Each checkpoint was reported.
