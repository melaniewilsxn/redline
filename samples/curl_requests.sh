#!/usr/bin/env bash
# Walk through the document API. Prints status codes and short JSON, not contract text.
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
workdir=$(mktemp -d)
trap 'rm -rf "$workdir"' EXIT

show_body() {
  python3 - "$workdir/body" <<'PY'
import json
import sys

raw = open(sys.argv[1]).read()
try:
    body = json.loads(raw)
except json.JSONDecodeError:
    print(raw[:300])
    raise SystemExit(1)

def trim(value):
    if isinstance(value, dict):
        trimmed = {}
        for key, item in value.items():
            if key == "text" and isinstance(item, str):
                trimmed[key] = f"<{len(item)} characters>"
            else:
                trimmed[key] = trim(item)
        return trimmed
    if isinstance(value, list):
        return [trim(item) for item in value]
    return value

print(json.dumps(trim(body), indent=2))
PY
}

header_value() {
  local name="$1"
  python3 - "$workdir/headers" "$name" <<'PY'
import sys

wanted = sys.argv[2].lower()
for line in open(sys.argv[1]):
    if line.lower().startswith(wanted + ":"):
        print(line.split(":", 1)[1].strip())
        break
else:
    raise SystemExit(f"missing header {sys.argv[2]}")
PY
}

require_error_type() {
  local expected="$1"
  python3 - "$workdir/body" "$expected" <<'PY'
import json
import sys

body = json.load(open(sys.argv[1]))
if body["error_type"] != sys.argv[2]:
    raise SystemExit(f"error_type was {body['error_type']}, expected {sys.argv[2]}")
print(f"error_type {body['error_type']}")
PY
}

call_api() {
  local name="$1"
  local expected="$2"
  shift 2
  echo
  echo "== $name =="
  local status
  status=$(curl -sS -D "$workdir/headers" -o "$workdir/body" -w "%{http_code}" "$@")
  echo "status $status"
  show_body
  if [[ "$status" != "$expected" ]]; then
    echo "expected status $expected" >&2
    exit 1
  fi
}

call_api "1. Create a short contract" 201 \
  -X POST "$BASE_URL/documents" \
  -H "Content-Type: application/json" \
  --data-binary @- <<'JSON'
{"title":"Curl demo","text":"Alpha. The Customer shall pay the invoice. Beta. The Customer shall keep records. Omega stays.","author":"Ada"}
JSON
document_id=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["id"])' "$workdir/body")
original_etag=$(header_value "etag")
echo "id $document_id"
echo "etag $original_etag"

call_api "2. Get the document" 200 "$BASE_URL/documents/$document_id"
echo "etag $(header_value etag)"

call_api "3. Patch an occurrence" 200 \
  -X PATCH "$BASE_URL/documents/$document_id" \
  -H "Content-Type: application/json" \
  -H "If-Match: $original_etag" \
  --data-binary @- <<'JSON'
{"author":"Ada","changes":[{"target":{"type":"occurrence","text":"The Customer shall","occurrence":2},"replacement":"The Customer must"}]}
JSON
etag_after_occurrence=$(header_value "etag")

call_api "4. Patch with context" 200 \
  -X PATCH "$BASE_URL/documents/$document_id" \
  -H "Content-Type: application/json" \
  -H "If-Match: $etag_after_occurrence" \
  --data-binary @- <<'JSON'
{"author":"Ada","changes":[{"target":{"type":"context","text":"The Customer shall","prefix":"Alpha. ","suffix":" pay the invoice."},"replacement":"The Customer will"}]}
JSON
etag_after_context=$(header_value "etag")

python3 - "$workdir/body" "$workdir/batch.json" <<'PY'
import json
import sys

body = json.load(open(sys.argv[1]))
text = body["document"]["text"]
alpha = text.index("Alpha. ")
omega = text.index("Omega")
changes = [
    {"target": {"type": "range", "start": alpha, "end": alpha + len("Alpha. ")}, "replacement": ""},
    {"target": {"type": "range", "start": omega, "end": omega + len("Omega")}, "replacement": "End"},
    {"target": {"type": "range", "start": len(text), "end": len(text)}, "replacement": "!"},
]
json.dump({"author": "Ada", "changes": changes}, open(sys.argv[2], "w"))
PY

call_api "5. Patch a mixed batch" 200 \
  -X PATCH "$BASE_URL/documents/$document_id" \
  -H "Content-Type: application/json" \
  -H "If-Match: $etag_after_context" \
  --data-binary @"$workdir/batch.json"
current_etag=$(header_value "etag")

call_api "6. Reuse the old ETag" 412 \
  -X PATCH "$BASE_URL/documents/$document_id" \
  -H "Content-Type: application/json" \
  -H "If-Match: $original_etag" \
  --data-binary @- <<'JSON'
{"author":"Ada","changes":[{"target":{"type":"range","start":0,"end":1},"replacement":"X"}]}
JSON
require_error_type "precondition_failed"

call_api "7. Omit If-Match" 428 \
  -X PATCH "$BASE_URL/documents/$document_id" \
  -H "Content-Type: application/json" \
  --data-binary @- <<'JSON'
{"author":"Ada","changes":[{"target":{"type":"range","start":0,"end":1},"replacement":"X"}]}
JSON
require_error_type "precondition_required"

call_api "8. Overlapping changes" 422 \
  -X PATCH "$BASE_URL/documents/$document_id" \
  -H "Content-Type: application/json" \
  -H "If-Match: $current_etag" \
  --data-binary @- <<'JSON'
{"author":"Ada","changes":[{"target":{"type":"range","start":0,"end":4},"replacement":"A"},{"target":{"type":"range","start":2,"end":6},"replacement":"B"}]}
JSON
require_error_type "overlapping_changes"

call_api "9. Text not found" 422 \
  -X PATCH "$BASE_URL/documents/$document_id" \
  -H "Content-Type: application/json" \
  -H "If-Match: $current_etag" \
  --data-binary @- <<'JSON'
{"author":"Ada","changes":[{"target":{"type":"occurrence","text":"this phrase is absent","occurrence":1},"replacement":"x"}]}
JSON
require_error_type "target_not_found"

call_api "10. Unknown document" 404 \
  "$BASE_URL/documents/00000000-0000-7000-8000-000000000099"
require_error_type "document_not_found"

call_api "11a. List versions" 200 "$BASE_URL/documents/$document_id/versions"
call_api "11b. Get version 1" 200 "$BASE_URL/documents/$document_id/versions/1"

call_api "12. Search for a word" 200 \
  --get "$BASE_URL/search" --data-urlencode "q=Customer"

call_api "13. Search for two words" 200 \
  --get "$BASE_URL/search" --data-urlencode "q=Customer invoice"

call_api "14. Search for a phrase" 200 \
  --get "$BASE_URL/search" --data-urlencode 'q="pay the invoice"'

call_api "15. Search selected documents" 200 \
  --get "$BASE_URL/search" \
  --data-urlencode "q=Customer" \
  --data-urlencode "document_ids=$document_id"

call_api "16. Search inside one document" 200 \
  --get "$BASE_URL/documents/$document_id/search" --data-urlencode "q=Customer"

call_api "17. Query with no words" 422 \
  --get "$BASE_URL/search" --data-urlencode 'q=""'
require_error_type "invalid_query"

echo
echo "== 18. Suggest redlines for the seeded MSA =="
status=$(curl -sS -D "$workdir/headers" -o "$workdir/body" -w "%{http_code}" \
  "$BASE_URL/documents?limit=100")
echo "status $status"
show_body
if [[ "$status" != "200" ]]; then
  echo "expected status 200" >&2
  exit 1
fi
agreement_id=$(python3 - "$workdir/body" <<'PY'
import json
import sys

body = json.load(open(sys.argv[1]))
for document in body["documents"]:
    if document["title"] == "Master Services Agreement":
        print(document["id"])
        break
else:
    raise SystemExit("seeded master services agreement was not found")
PY
)
status=$(curl -sS -D "$workdir/headers" -o "$workdir/body" -w "%{http_code}" \
  -X POST "$BASE_URL/documents/$agreement_id/ai-redlines" \
  -H "Content-Type: application/json" \
  --data-binary '{"instruction":"Make the indemnification mutual"}')
echo "status $status"
show_body
if [[ "$status" == "503" ]]; then
  require_error_type "ai_not_configured"
  echo "AI redlines are not configured; skipping apply"
elif [[ "$status" == "200" ]]; then
  python3 - "$workdir/body" "$workdir/apply.json" <<'PY'
import json
import sys

body = json.load(open(sys.argv[1]))
print(f"suggestions {len(body['suggestions'])}")
print(f"dropped {len(body['dropped'])}")
changes = []
for suggestion in body["suggestions"]:
    print(f"{suggestion['original_text']} -> {suggestion['replacement']}")
    changes.append(
        {
            "target": {
                "type": "range",
                "start": suggestion["start"],
                "end": suggestion["end"],
            },
            "replacement": suggestion["replacement"],
        }
    )
if changes:
    json.dump({"author": "Ada", "changes": changes}, open(sys.argv[2], "w"))
PY
  if [[ -f "$workdir/apply.json" ]]; then
    suggestion_etag=$(header_value "etag")
    call_api "18b. Apply the suggestions" 200 \
      -X PATCH "$BASE_URL/documents/$agreement_id" \
      -H "Content-Type: application/json" \
      -H "If-Match: $suggestion_etag" \
      --data-binary @"$workdir/apply.json"
  else
    echo "No anchored suggestions to apply"
  fi
else
  echo "expected status 200 or 503" >&2
  exit 1
fi

echo
echo "Curl walkthrough finished."
