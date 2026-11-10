import uuid
from dataclasses import asdict, dataclass
from http import HTTPStatus

import psycopg
from fastapi.testclient import TestClient

from redline.api.schemas import (
    ApplyChangesRequest,
    ChangeRequest,
    ChangeTargetType,
    CreateDocumentRequest,
    ErrorType,
    RangeTargetRequest,
)
from redline.config import Settings
from redline.main import create_app
from redline.storage.database import apply_schema
from redline.storage.document_repository import (
    INITIAL_DOCUMENT_VERSION,
    insert_document,
    insert_document_version,
)

CREATED_SUMMARY = "Created document"
QUERY_OVER_MAXIMUM = "a" * 501
DOCUMENT_TITLE = "Notes"
DOCUMENT_AUTHOR = "Ada"


@dataclass(frozen=True)
class CreatedDocument:
    """The id and text of a document created through the API."""

    document_id: str
    text: str


def post_document(client: TestClient, title: str, text: str, author: str) -> CreatedDocument:
    """Create a document and return its id and text."""
    request = CreateDocumentRequest(title=title, text=text, author=author)
    response = client.post("/documents", json=asdict(request))
    assert response.status_code == HTTPStatus.CREATED
    body = response.json()
    return CreatedDocument(document_id=body["id"], text=body["text"])


def test_search_finds_created_document(client: TestClient) -> None:
    """A document created through the API is found by a word in its text."""
    created = post_document(
        client, DOCUMENT_TITLE, "The escrow agent holds funds.", DOCUMENT_AUTHOR
    )

    response = client.get("/search", params={"q": "escrow"})

    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert created.document_id in [hit["document_id"] for hit in body["hits"]]
    assert body["total_count"] >= 1


def test_search_reflects_patch_immediately(client: TestClient) -> None:
    """A removed word stops matching, and an added word starts, on the same server."""
    created = post_document(client, DOCUMENT_TITLE, "Hello alpha", DOCUMENT_AUTHOR)
    request = ApplyChangesRequest(
        author=DOCUMENT_AUTHOR,
        changes=[
            ChangeRequest(
                target=RangeTargetRequest(type=ChangeTargetType.RANGE, start=6, end=11),
                replacement="beta",
            )
        ],
    )
    patched = client.patch(
        f"/documents/{created.document_id}",
        headers={"If-Match": f'"{created.document_id}-1"'},
        json=asdict(request),
    )

    removed = client.get("/search", params={"q": "alpha"})
    added = client.get("/search", params={"q": "beta"})

    assert patched.status_code == HTTPStatus.OK
    assert created.document_id not in [hit["document_id"] for hit in removed.json()["hits"]]
    assert created.document_id in [hit["document_id"] for hit in added.json()["hits"]]


def test_search_with_document_ids_limits_results(client: TestClient) -> None:
    """document_ids returns only the selected document."""
    first = post_document(client, DOCUMENT_TITLE, "quartz appears once", DOCUMENT_AUTHOR)
    second = post_document(client, DOCUMENT_TITLE, "quartz appears twice", DOCUMENT_AUTHOR)

    response = client.get("/search", params={"q": "quartz", "document_ids": second.document_id})

    assert response.status_code == HTTPStatus.OK
    assert [hit["document_id"] for hit in response.json()["hits"]] == [second.document_id]
    assert first.document_id not in [hit["document_id"] for hit in response.json()["hits"]]


def test_document_search_returns_only_that_document(client: TestClient) -> None:
    """A per-document search does not return another document with the same word."""
    first = post_document(client, DOCUMENT_TITLE, "shared token here", DOCUMENT_AUTHOR)
    post_document(client, DOCUMENT_TITLE, "shared token there", DOCUMENT_AUTHOR)

    response = client.get(f"/documents/{first.document_id}/search", params={"q": "shared"})

    assert response.status_code == HTTPStatus.OK
    assert [hit["document_id"] for hit in response.json()["hits"]] == [first.document_id]


def test_document_search_for_missing_document_returns_404(client: TestClient) -> None:
    """Searching a document that is not indexed returns document_not_found."""
    response = client.get(f"/documents/{uuid.uuid4()}/search", params={"q": "alpha"})

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()["error_type"] == ErrorType.DOCUMENT_NOT_FOUND


def test_empty_query_returns_422_invalid_query(client: TestClient) -> None:
    """An empty q fails validation, and a query with no words returns invalid_query."""
    empty = client.get("/search", params={"q": ""})
    punctuation = client.get("/search", params={"q": '""'})

    assert empty.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
    assert empty.json()["error_type"] == ErrorType.VALIDATION_ERROR
    assert punctuation.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
    assert punctuation.json()["error_type"] == ErrorType.INVALID_QUERY


def test_query_over_maximum_length_returns_validation_error(client: TestClient) -> None:
    """A query longer than the maximum is a validation error."""
    response = client.get("/search", params={"q": QUERY_OVER_MAXIMUM})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
    assert response.json()["error_type"] == ErrorType.VALIDATION_ERROR


def test_malformed_document_id_filter_returns_validation_error(client: TestClient) -> None:
    """A document id that is not a UUID is a validation error."""
    response = client.get("/search", params={"q": "alpha", "document_ids": "not-a-uuid"})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
    assert response.json()["error_type"] == ErrorType.VALIDATION_ERROR


def test_limit_above_maximum_returns_validation_error(client: TestClient) -> None:
    """A limit above the maximum is a validation error."""
    response = client.get("/search", params={"q": "alpha", "limit": 101})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
    assert response.json()["error_type"] == ErrorType.VALIDATION_ERROR


def test_page_past_end_keeps_total_count(client: TestClient) -> None:
    """A page past the end is empty, and total_count still counts the match."""
    post_document(client, DOCUMENT_TITLE, "uniquevioletword appears once", DOCUMENT_AUTHOR)

    response = client.get("/search", params={"q": "uniquevioletword", "offset": 50})

    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert body["hits"] == []
    assert body["total_count"] == 1


def test_highlight_offsets_point_at_the_matched_text(client: TestClient) -> None:
    """Each highlight slice is the matched word."""
    created = post_document(client, DOCUMENT_TITLE, "The Customer shall pay.", DOCUMENT_AUTHOR)

    response = client.get("/search", params={"q": "Customer"})

    assert response.status_code == HTTPStatus.OK
    hits = [hit for hit in response.json()["hits"] if hit["document_id"] == created.document_id]
    assert len(hits) == 1
    highlights = [
        highlight for snippet in hits[0]["snippets"] for highlight in snippet["highlights"]
    ]
    assert highlights
    for highlight in highlights:
        assert created.text[highlight["start"] : highlight["end"]] == "Customer"


def test_index_is_built_from_database_at_startup(
    test_database_url: str, test_settings: Settings
) -> None:
    """A committed document is searchable after a fresh process starts, then it is deleted."""
    document_id = uuid.uuid7()
    title = f"Startup {document_id}"
    word = f"word{document_id.hex}"
    text = f"The {word} is here."
    with psycopg.connect(test_database_url, autocommit=True) as connection:
        apply_schema(connection)
        insert_document(connection, document_id, title)
        insert_document_version(
            connection,
            document_id,
            INITIAL_DOCUMENT_VERSION,
            text,
            DOCUMENT_AUTHOR,
            CREATED_SUMMARY,
        )
    try:
        with TestClient(create_app(test_settings), raise_server_exceptions=False) as fresh_client:
            response = fresh_client.get("/search", params={"q": word})
        matching = [
            hit for hit in response.json()["hits"] if hit["document_id"] == str(document_id)
        ]
        assert response.status_code == HTTPStatus.OK
        assert len(matching) == 1
        assert matching[0]["title"] == title
    finally:
        with psycopg.connect(test_database_url, autocommit=True) as connection:
            connection.execute("DELETE FROM documents WHERE id = %s", (document_id,))
