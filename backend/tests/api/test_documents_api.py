import uuid
from http import HTTPStatus

import httpx
from fastapi.testclient import TestClient
from psycopg import Connection

from redline.api.dependencies import get_connection
from redline.api.schemas import ErrorType

CONTRACT = "Alpha. The Customer shall pay. Beta. The Customer shall wait."


def post_document(
    client: TestClient, title: str = "Notes", text: str = CONTRACT, author: str = "Ada"
) -> httpx.Response:
    """Create a document through the API."""
    return client.post(
        "/documents",
        json={"title": title, "text": text, "author": author},
    )


def patch_document(
    client: TestClient,
    document_id: str,
    etag: str,
    changes: list[dict[str, object]],
    author: str = "Ada",
) -> httpx.Response:
    """Apply changes with If-Match."""
    return client.patch(
        f"/documents/{document_id}",
        headers={"If-Match": etag},
        json={"author": author, "changes": changes},
    )


def test_create_document_returns_201_with_etag_and_location(client: TestClient) -> None:
    """Creating a document returns 201, an ETag, and a Location header."""
    response = post_document(client, text="Hello")

    body = response.json()
    assert response.status_code == HTTPStatus.CREATED
    assert body["title"] == "Notes"
    assert body["text"] == "Hello"
    assert body["version"] == 1
    assert response.headers["etag"] == f'"{body["id"]}-1"'
    assert response.headers["location"] == f"/documents/{body['id']}"


def test_create_document_with_empty_title_returns_validation_error(client: TestClient) -> None:
    """An empty title is rejected as a validation error."""
    response = post_document(client, title="")

    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
    assert response.json()["error_type"] == ErrorType.VALIDATION_ERROR
    assert response.json()["code"] == HTTPStatus.UNPROCESSABLE_CONTENT


def test_get_document_returns_text_and_etag(client: TestClient) -> None:
    """Reading a document returns its text and ETag."""
    created = post_document(client, text="Hello").json()

    response = client.get(f"/documents/{created['id']}")

    assert response.status_code == HTTPStatus.OK
    assert response.json()["text"] == "Hello"
    assert response.headers["etag"] == f'"{created["id"]}-1"'


def test_get_missing_document_returns_404_document_not_found(client: TestClient) -> None:
    """An unknown document id returns 404 document_not_found."""
    response = client.get(f"/documents/{uuid.uuid4()}")

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()["error_type"] == ErrorType.DOCUMENT_NOT_FOUND
    assert response.json()["code"] == HTTPStatus.NOT_FOUND


def test_get_document_with_malformed_id_returns_validation_error(client: TestClient) -> None:
    """A path id that is not a UUID is a validation error."""
    response = client.get("/documents/not-a-uuid")

    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
    assert response.json()["error_type"] == ErrorType.VALIDATION_ERROR


def test_list_documents_includes_created_document(client: TestClient) -> None:
    """The document list includes a document created in this test."""
    created = post_document(client, text="Hello").json()

    response = client.get("/documents")

    body = response.json()
    assert response.status_code == HTTPStatus.OK
    assert created["id"] in [document["id"] for document in body["documents"]]
    assert body["total_count"] >= 1


def test_list_documents_with_limit_above_maximum_returns_validation_error(
    client: TestClient,
) -> None:
    """A limit above the maximum is a validation error."""
    response = client.get("/documents", params={"limit": 101})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
    assert response.json()["error_type"] == ErrorType.VALIDATION_ERROR


def test_patch_with_range_target_returns_updated_text_and_new_etag(client: TestClient) -> None:
    """A range replacement updates the text and returns a new ETag."""
    created = post_document(client, text="abcdefghij").json()
    etag = f'"{created["id"]}-1"'

    response = patch_document(
        client,
        created["id"],
        etag,
        [{"target": {"type": "range", "start": 0, "end": 4}, "replacement": "XYZ"}],
    )

    body = response.json()
    assert response.status_code == HTTPStatus.OK
    assert body["document"]["text"] == "XYZefghij"
    assert body["document"]["version"] == 2
    assert response.headers["etag"] == f'"{created["id"]}-2"'


def test_patch_with_occurrence_target_replaces_that_occurrence(client: TestClient) -> None:
    """An occurrence target replaces that match and leaves the earlier one."""
    created = post_document(client, text="The Seller shall pay. The Seller shall wait.").json()

    response = patch_document(
        client,
        created["id"],
        f'"{created["id"]}-1"',
        [
            {
                "target": {"type": "occurrence", "text": "Seller", "occurrence": 2},
                "replacement": "Vendor",
            }
        ],
    )

    assert response.json()["document"]["text"] == "The Seller shall pay. The Vendor shall wait."


def test_patch_with_context_target_replaces_matching_phrase(client: TestClient) -> None:
    """A context target replaces the phrase between its prefix and suffix."""
    created = post_document(client).json()

    response = patch_document(
        client,
        created["id"],
        f'"{created["id"]}-1"',
        [
            {
                "target": {
                    "type": "context",
                    "text": "The Customer shall",
                    "prefix": "Beta. ",
                    "suffix": " wait.",
                },
                "replacement": "The Customer must",
            }
        ],
    )

    assert (
        response.json()["document"]["text"]
        == "Alpha. The Customer shall pay. Beta. The Customer must wait."
    )


def test_patch_batch_reports_applied_edits_in_pre_batch_offsets(client: TestClient) -> None:
    """Applied edits keep the offsets from before the batch, in position order."""
    created = post_document(client, text="abcdefghij").json()

    response = patch_document(
        client,
        created["id"],
        f'"{created["id"]}-1"',
        [
            {"target": {"type": "range", "start": 6, "end": 8}, "replacement": "XY"},
            {"target": {"type": "range", "start": 1, "end": 3}, "replacement": "Q"},
        ],
    )

    body = response.json()
    assert body["document"]["text"] == "aQdefXYij"
    assert [
        (edit["start"], edit["end"], edit["replacement_length"]) for edit in body["applied_edits"]
    ] == [
        (1, 3, 1),
        (6, 8, 2),
    ]


def test_patch_without_if_match_returns_428(client: TestClient) -> None:
    """A patch with no If-Match header returns 428."""
    created = post_document(client, text="Hello").json()

    response = client.patch(
        f"/documents/{created['id']}",
        json={
            "author": "Ada",
            "changes": [{"target": {"type": "range", "start": 0, "end": 1}, "replacement": "J"}],
        },
    )

    assert response.status_code == HTTPStatus.PRECONDITION_REQUIRED
    assert response.json()["error_type"] == ErrorType.PRECONDITION_REQUIRED
    assert response.json()["code"] == HTTPStatus.PRECONDITION_REQUIRED


def test_patch_with_stale_if_match_returns_412(client: TestClient) -> None:
    """An If-Match for a version that was never current returns 412."""
    created = post_document(client, text="Hello").json()

    response = patch_document(
        client,
        created["id"],
        f'"{created["id"]}-9"',
        [{"target": {"type": "range", "start": 0, "end": 1}, "replacement": "J"}],
    )

    assert response.status_code == HTTPStatus.PRECONDITION_FAILED
    assert response.json()["error_type"] == ErrorType.PRECONDITION_FAILED


def test_patch_with_other_documents_etag_returns_412(client: TestClient) -> None:
    """An ETag that names a different document returns 412."""
    first = post_document(client, text="Hello").json()
    second = post_document(client, text="Hello").json()

    response = patch_document(
        client,
        second["id"],
        f'"{first["id"]}-1"',
        [{"target": {"type": "range", "start": 0, "end": 1}, "replacement": "J"}],
    )

    assert response.status_code == HTTPStatus.PRECONDITION_FAILED
    assert response.json()["error_type"] == ErrorType.PRECONDITION_FAILED


def test_second_patch_with_same_if_match_returns_412(client: TestClient) -> None:
    """Reusing an ETag after a successful write returns 412."""
    created = post_document(client, text="Hello").json()
    etag = f'"{created["id"]}-1"'
    change = [{"target": {"type": "range", "start": 0, "end": 1}, "replacement": "J"}]
    first = patch_document(client, created["id"], etag, change)

    second = patch_document(client, created["id"], etag, change)

    assert first.status_code == HTTPStatus.OK
    assert second.status_code == HTTPStatus.PRECONDITION_FAILED
    assert second.json()["error_type"] == ErrorType.PRECONDITION_FAILED


def test_patch_with_overlapping_changes_returns_422_overlapping_changes(client: TestClient) -> None:
    """Overlapping ranges reject the whole batch."""
    created = post_document(client, text="abcdefghij").json()

    response = patch_document(
        client,
        created["id"],
        f'"{created["id"]}-1"',
        [
            {"target": {"type": "range", "start": 0, "end": 4}, "replacement": "A"},
            {"target": {"type": "range", "start": 2, "end": 6}, "replacement": "B"},
        ],
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
    assert response.json()["error_type"] == ErrorType.OVERLAPPING_CHANGES
    assert client.get(f"/documents/{created['id']}").json()["version"] == 1


def test_patch_with_missing_text_returns_422_target_not_found(client: TestClient) -> None:
    """Text that is not in the document returns target_not_found."""
    created = post_document(client, text="Hello").json()

    response = patch_document(
        client,
        created["id"],
        f'"{created["id"]}-1"',
        [
            {
                "target": {"type": "occurrence", "text": "missing", "occurrence": 1},
                "replacement": "x",
            }
        ],
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
    assert response.json()["error_type"] == ErrorType.TARGET_NOT_FOUND


def test_patch_with_ambiguous_context_returns_422_ambiguous_target(client: TestClient) -> None:
    """A context target that matches twice returns ambiguous_target."""
    created = post_document(client, text="Hello Hello").json()

    response = patch_document(
        client,
        created["id"],
        f'"{created["id"]}-1"',
        [
            {
                "target": {"type": "context", "text": "Hello", "prefix": "", "suffix": ""},
                "replacement": "Hi",
            }
        ],
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
    assert response.json()["error_type"] == ErrorType.AMBIGUOUS_TARGET


def test_patch_with_invalid_range_returns_422_invalid_target(client: TestClient) -> None:
    """A range whose start is after its end returns invalid_target."""
    created = post_document(client, text="Hello").json()

    response = patch_document(
        client,
        created["id"],
        f'"{created["id"]}-1"',
        [{"target": {"type": "range", "start": 4, "end": 1}, "replacement": "x"}],
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
    assert response.json()["error_type"] == ErrorType.INVALID_TARGET


def test_patch_with_range_past_end_returns_422_range_out_of_bounds(client: TestClient) -> None:
    """A range that ends past the document returns range_out_of_bounds."""
    created = post_document(client, text="Hello").json()

    response = patch_document(
        client,
        created["id"],
        f'"{created["id"]}-1"',
        [{"target": {"type": "range", "start": 0, "end": 100}, "replacement": "x"}],
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
    assert response.json()["error_type"] == ErrorType.RANGE_OUT_OF_BOUNDS


def test_patch_with_empty_changes_returns_validation_error(client: TestClient) -> None:
    """A patch with no changes is a validation error."""
    created = post_document(client, text="Hello").json()

    response = patch_document(client, created["id"], f'"{created["id"]}-1"', [])

    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
    assert response.json()["error_type"] == ErrorType.VALIDATION_ERROR


def test_patch_with_unknown_target_type_returns_validation_error(client: TestClient) -> None:
    """An unknown target type is a validation error."""
    created = post_document(client, text="Hello").json()

    response = patch_document(
        client,
        created["id"],
        f'"{created["id"]}-1"',
        [{"target": {"type": "nope", "text": "Hello"}, "replacement": "x"}],
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
    assert response.json()["error_type"] == ErrorType.VALIDATION_ERROR
    assert response.json()["code"] == HTTPStatus.UNPROCESSABLE_CONTENT


def test_patch_missing_document_returns_404(client: TestClient) -> None:
    """Patching an unknown document returns 404."""
    document_id = uuid.uuid4()

    response = patch_document(
        client,
        str(document_id),
        f'"{document_id}-1"',
        [{"target": {"type": "range", "start": 0, "end": 1}, "replacement": "J"}],
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()["error_type"] == ErrorType.DOCUMENT_NOT_FOUND


def test_list_versions_after_patch_shows_both_versions(client: TestClient) -> None:
    """After a patch, both versions are listed with the newest first."""
    created = post_document(client, text="Hello").json()
    patch_document(
        client,
        created["id"],
        f'"{created["id"]}-1"',
        [{"target": {"type": "range", "start": 0, "end": 1}, "replacement": "J"}],
    )

    response = client.get(f"/documents/{created['id']}/versions")

    assert response.status_code == HTTPStatus.OK
    assert [version["version"] for version in response.json()] == [2, 1]


def test_get_version_one_after_patch_returns_original_text(client: TestClient) -> None:
    """Version 1 still has the text from before the patch."""
    created = post_document(client, text="Hello").json()
    patch_document(
        client,
        created["id"],
        f'"{created["id"]}-1"',
        [{"target": {"type": "range", "start": 0, "end": 1}, "replacement": "J"}],
    )

    response = client.get(f"/documents/{created['id']}/versions/1")

    assert response.status_code == HTTPStatus.OK
    assert response.json()["text"] == "Hello"
    assert response.json()["author"] == "Ada"


def test_get_missing_version_returns_404_version_not_found(client: TestClient) -> None:
    """A version number the document does not have returns version_not_found."""
    created = post_document(client, text="Hello").json()

    response = client.get(f"/documents/{created['id']}/versions/9")

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()["error_type"] == ErrorType.VERSION_NOT_FOUND
    assert response.json()["code"] == HTTPStatus.NOT_FOUND


def test_unexpected_error_returns_500_internal_error(client: TestClient) -> None:
    """An unexpected error returns internal_error, and the next request still works."""
    original = client.app.dependency_overrides[get_connection]

    def raise_runtime_error() -> Connection:
        """Fail this request before it reaches the database."""
        raise RuntimeError("database exploded")

    client.app.dependency_overrides[get_connection] = raise_runtime_error
    failed = client.get("/health")
    client.app.dependency_overrides[get_connection] = original

    recovered = client.get("/health")

    assert failed.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert failed.json()["error_type"] == ErrorType.INTERNAL_ERROR
    assert failed.json()["code"] == HTTPStatus.INTERNAL_SERVER_ERROR
    assert "database exploded" not in failed.text
    assert recovered.status_code == HTTPStatus.OK


def test_health_returns_ok(client: TestClient) -> None:
    """The health check reports ok when the database accepts a statement."""
    response = client.get("/health")

    assert response.status_code == HTTPStatus.OK
    assert response.json()["status"] == "ok"


def test_unknown_path_returns_404_http_error(client: TestClient) -> None:
    """An unknown path returns http_error with status 404."""
    response = client.get("/no-such-path")

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()["error_type"] == ErrorType.HTTP_ERROR
    assert response.json()["code"] == HTTPStatus.NOT_FOUND


def test_wrong_method_returns_405_http_error(client: TestClient) -> None:
    """The wrong method returns http_error with status 405."""
    response = client.post("/health")

    assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED
    assert response.json()["error_type"] == ErrorType.HTTP_ERROR
    assert response.json()["code"] == HTTPStatus.METHOD_NOT_ALLOWED
