# Redline

## What it is

Redline stores plain-text contracts and applies batches of edits. Each edit points at text by a character range, by the nth exact match, or by the words around a phrase. A write saves a new full version only when the document is still the version the client read.

## Setup

```bash
cp .env.example .env
make db-up
make install
make seed
make dev
```

API docs are at http://localhost:8000/docs.

Postgres listens on port 5433 so it does not collide with a Postgres already on 5432. `make db-up` creates two databases, `redline` and `redline_test`.

To use your own Postgres, create a role and both databases, then point `DATABASE_URL` and `TEST_DATABASE_URL` in `.env` at them. The app creates the tables on startup. Tests create them too, and they roll their writes back.

## Usage

Create a document:

```bash
curl -sS -D - -o /tmp/document.json \
  -X POST http://localhost:8000/documents \
  -H "Content-Type: application/json" \
  --data '{"title":"Demo","text":"Alpha. The Customer shall pay. Beta. The Customer shall wait.","author":"Ada"}'
```

The response headers include `ETag` and `Location`. Read it back:

```bash
curl -sS -D - http://localhost:8000/documents/DOCUMENT_ID
```

Send edits with `PATCH` and the `ETag` you just received in `If-Match`. A range replaces those characters (an empty replacement deletes; the same start and end inserts):

```bash
curl -sS -X PATCH http://localhost:8000/documents/DOCUMENT_ID \
  -H "Content-Type: application/json" \
  -H "If-Match: \"DOCUMENT_ID-1\"" \
  --data '{"author":"Ada","changes":[{"target":{"type":"range","start":0,"end":5},"replacement":"First"}]}'
```

An occurrence replaces one exact match. This changes the second "The Customer shall":

```bash
curl -sS -X PATCH http://localhost:8000/documents/DOCUMENT_ID \
  -H "Content-Type: application/json" \
  -H "If-Match: \"DOCUMENT_ID-1\"" \
  --data '{"author":"Ada","changes":[{"target":{"type":"occurrence","text":"The Customer shall","occurrence":2},"replacement":"The Customer must"}]}'
```

Context replaces the match that sits between a prefix and a suffix, so a repeated phrase still names one clause:

```bash
curl -sS -X PATCH http://localhost:8000/documents/DOCUMENT_ID \
  -H "Content-Type: application/json" \
  -H "If-Match: \"DOCUMENT_ID-1\"" \
  --data '{"author":"Ada","changes":[{"target":{"type":"context","text":"The Customer shall","prefix":"Alpha. ","suffix":" pay."},"replacement":"The Customer will"}]}'
```

`samples/curl_requests.sh` walks through create, all three target types, a mixed batch, a stale `If-Match` (412), a missing `If-Match` (428), an overlap (422), missing text (422), an unknown id (404), and version history.

## API design

Each noun is one resource: documents, and versions nested under a document. A read that is a single query calls the repository directly. A write goes through the document service, which is the only place that applies edits.

Edits use `PATCH` because the body is a partial change to the text, described by our own JSON. It is not a full replacement of the document, and it is not JSON Patch: JSON Patch paths address JSON fields, not spans of the document text.

A change has no `operation` field. Every change means "replace this span." An empty replacement deletes. A target whose start and end are the same inserts. The span can be named in three ways, because lawyers edit wording rather than offsets. A range is exact and breaks if anything earlier in the document changes. An occurrence number is easy to type and shifts when another match is added above it. Context, a prefix and a suffix in the style of the W3C TextQuoteSelector, survives most edits elsewhere and says which copy is meant.

A batch is atomic. Every target is resolved against the current text before any new text is built. If one target is missing, ambiguous, or overlapping, nothing is saved.

Reads return a strong ETag, `"<document id>-<version>"`. A write must send that value in `If-Match`. The service checks the version before it does the work, then claims the next version with `UPDATE ... WHERE current_version = <expected>` inside a short transaction. The first writer wins. A second writer, or a stale, weak, wildcard, or foreign ETag, gets 412. A missing `If-Match` gets 428.

Every error body is JSON:

```json
{"error": "A readable message", "code": 422, "error_type": "target_not_found"}
```

| Status | `error_type` | When |
| --- | --- | --- |
| 422 | `validation_error` | The JSON does not match the request shape |
| 422 | `invalid_target` | A target is malformed, such as a start after its end |
| 422 | `range_out_of_bounds` | A range ends past the document |
| 422 | `target_not_found` | The text or occurrence is not there |
| 422 | `ambiguous_target` | A context matches more than once |
| 422 | `overlapping_changes` | Two changes cover the same character, or both insert at the same place |
| 404 | `document_not_found` | No document with that id |
| 404 | `version_not_found` | That document has no such version |
| 412 | `precondition_failed` | `If-Match` is stale or not one of our ETags |
| 428 | `precondition_required` | `If-Match` was omitted |
| 404, 405, others | `http_error` | The path or method does not exist |
| 500 | `internal_error` | Anything else. The message is always "Internal server error" |

## Performance

Applying changes one at a time would copy the whole document for each change. The engine resolves every target first, sorts the spans, and joins slices once. That rebuild is linear in the document length plus the number of changes. Each text target is a scan of the document, so resolution grows with the document length times the number of text targets. Range targets are constant time. `AppliedEdit` offsets refer to the text from before the batch, so a later step can move other spans without replaying the edits.

The edit is computed with no transaction open. The compare-and-swap is one update that both checks and claims the next version, so a 10MB rebuild does not hold a row lock. Versions store the full text, which is simple and exact. At 10MB times many versions that cost is real; storing deltas is a later step.

On this machine, a pytest run measured two 10MB cases. Applying 1,000 range changes and checking them against a one-change-at-a-time rebuild took 0.42 seconds (`test_thousand_range_changes_match_one_at_a_time_reference`). Creating a 10MB document, applying 200 occurrence changes through the API, and reading version 2 back took 0.38 seconds (`test_large_document_round_trip_through_api`).

Routes are synchronous. psycopg is synchronous, and FastAPI runs sync routes in a thread pool, so the server does not mix async and blocking database calls.

## Testing

`make test` runs the suite. Tests that write to Postgres use `TEST_DATABASE_URL` and roll the transaction back, so they leave the test database empty. `make lint` runs Ruff.

## Next steps

- Auth, users, and per-document permissions. The author is a plain name field.
- Rich text and .docx import and export. Documents are plain text.
- Comment threads separate from proposal rationales.
- Search over the contracts, including an index that updates after a write, and embedding-based semantic search with hybrid re-ranking.
- Proposals, moving them forward when an edit lands, and accept and reject.
- Comparing two versions.
- AI redline suggestions.
- Multi-pattern target resolution (Aho–Corasick) for very large batches of text-targeted changes.
- Multi-process deployment. A later in-process search index assumes a single server.
- Storing versions as deltas instead of full copies.
