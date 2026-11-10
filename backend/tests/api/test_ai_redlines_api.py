from dataclasses import asdict
from http import HTTPStatus
from uuid import UUID

from fastapi.testclient import TestClient
from httpx import Response

from redline.ai.errors import ModelResponseError, ModelResponseFailure, ModelUnavailableError
from redline.ai.model_client import RedlineModelClient
from redline.ai.models import RedlineSuggestion
from redline.api.dependencies import get_model_client
from redline.api.schemas import (
    AiRedlineRequest,
    ApplyChangesRequest,
    ChangeRequest,
    ChangeTargetType,
    CreateDocumentRequest,
    ErrorType,
    RangeTargetRequest,
)
from tests.api.test_search_api import CreatedDocument
from tests.fixtures.fake_model_client import FailingModelClient, FakeModelClient

DOCUMENT_TITLE = "Notes"
DOCUMENT_AUTHOR = "Ada"
CONTRACT = "The Customer shall indemnify the Company."
INSTRUCTION = "Make the indemnification mutual"
MISSING_DOCUMENT_ID = UUID("00000000-0000-7000-8000-000000000099")


def test_ai_redlines_returns_suggestions_dropped_and_etag(client: TestClient) -> None:
    """A request returns anchored suggestions, dropped ones, and the version ETag."""
    created = post_document(client, CONTRACT)
    install_model(
        client,
        FakeModelClient(
            suggestions=[
                RedlineSuggestion(
                    text="indemnify the Company",
                    prefix="shall ",
                    suffix=".",
                    replacement="defend the Company",
                    rationale="Make the indemnity mutual.",
                    title="Make the indemnity mutual",
                ),
                RedlineSuggestion(
                    text="not in the document",
                    prefix="",
                    suffix="",
                    replacement="gone",
                    rationale="This quote is absent.",
                    title="Remove the missing quote",
                ),
            ]
        ),
    )

    response = post_redlines(client, created.document_id, INSTRUCTION)

    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert body["document_id"] == created.document_id
    assert body["version"] == 1
    assert response.headers["etag"] == f'"{created.document_id}-1"'
    assert len(body["suggestions"]) == 1
    assert body["suggestions"][0]["original_text"] == "indemnify the Company"
    assert body["suggestions"][0]["replacement"] == "defend the Company"
    assert body["dropped"][0]["reason"] == "target_not_found"


def test_applying_suggestions_through_patch_updates_the_document(client: TestClient) -> None:
    """Accepted suggestions apply as one range patch with the returned ETag."""
    created = post_document(client, "The Customer shall pay.")
    install_model(
        client,
        FakeModelClient(
            suggestions=[
                RedlineSuggestion(
                    text="shall",
                    prefix="Customer ",
                    suffix=" pay",
                    replacement="must",
                    rationale="Prefer must.",
                    title="Prefer must",
                )
            ]
        ),
    )
    suggested = post_redlines(client, created.document_id, INSTRUCTION)
    suggestion = suggested.json()["suggestions"][0]
    request = ApplyChangesRequest(
        author=DOCUMENT_AUTHOR,
        changes=[
            ChangeRequest(
                target=RangeTargetRequest(
                    type=ChangeTargetType.RANGE,
                    start=suggestion["start"],
                    end=suggestion["end"],
                ),
                replacement=suggestion["replacement"],
            )
        ],
    )

    response = client.patch(
        f"/documents/{created.document_id}",
        headers={"If-Match": suggested.headers["etag"]},
        json=asdict(request),
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json()["document"]["text"] == "The Customer must pay."


def test_applying_suggestions_after_document_changed_returns_412(client: TestClient) -> None:
    """Applying suggestions after another edit returns 412."""
    created = post_document(client, "The Customer shall pay.")
    install_model(
        client,
        FakeModelClient(
            suggestions=[
                RedlineSuggestion(
                    text="shall",
                    prefix="Customer ",
                    suffix=" pay",
                    replacement="must",
                    rationale="Prefer must.",
                    title="Prefer must",
                )
            ]
        ),
    )
    suggested = post_redlines(client, created.document_id, INSTRUCTION)
    etag = suggested.headers["etag"]
    suggestion = suggested.json()["suggestions"][0]
    first_edit = ApplyChangesRequest(
        author=DOCUMENT_AUTHOR,
        changes=[
            ChangeRequest(
                target=RangeTargetRequest(type=ChangeTargetType.RANGE, start=0, end=3),
                replacement="Our",
            )
        ],
    )
    client.patch(
        f"/documents/{created.document_id}",
        headers={"If-Match": etag},
        json=asdict(first_edit),
    )
    stale_edit = ApplyChangesRequest(
        author=DOCUMENT_AUTHOR,
        changes=[
            ChangeRequest(
                target=RangeTargetRequest(
                    type=ChangeTargetType.RANGE,
                    start=suggestion["start"],
                    end=suggestion["end"],
                ),
                replacement=suggestion["replacement"],
            )
        ],
    )

    response = client.patch(
        f"/documents/{created.document_id}",
        headers={"If-Match": etag},
        json=asdict(stale_edit),
    )

    assert response.status_code == HTTPStatus.PRECONDITION_FAILED
    assert response.json()["error_type"] == ErrorType.PRECONDITION_FAILED


def test_ai_redlines_for_missing_document_returns_404(client: TestClient) -> None:
    """An unknown document is a 404."""
    install_model(client, FakeModelClient(suggestions=[]))

    response = post_redlines(client, str(MISSING_DOCUMENT_ID), INSTRUCTION)

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()["error_type"] == ErrorType.DOCUMENT_NOT_FOUND


def test_ai_redlines_without_api_key_returns_503(client: TestClient) -> None:
    """No API key returns 503."""
    created = post_document(client, CONTRACT)

    response = post_redlines(client, created.document_id, INSTRUCTION)

    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert response.json()["error_type"] == ErrorType.AI_NOT_CONFIGURED


def test_model_failure_returns_502_model_unavailable(client: TestClient) -> None:
    """A failed model call returns 502 model_unavailable."""
    created = post_document(client, CONTRACT)
    install_model(client, FailingModelClient(ModelUnavailableError("APIStatusError")))

    response = post_redlines(client, created.document_id, INSTRUCTION)

    assert response.status_code == HTTPStatus.BAD_GATEWAY
    assert response.json()["error_type"] == ErrorType.MODEL_UNAVAILABLE


def test_invalid_model_response_returns_502_model_response_invalid(client: TestClient) -> None:
    """An unusable model response returns 502 model_response_invalid."""
    created = post_document(client, CONTRACT)
    install_model(client, FailingModelClient(ModelResponseError(ModelResponseFailure.INVALID_JSON)))

    response = post_redlines(client, created.document_id, INSTRUCTION)

    assert response.status_code == HTTPStatus.BAD_GATEWAY
    assert response.json()["error_type"] == ErrorType.MODEL_RESPONSE_INVALID


def test_empty_instruction_returns_validation_error(client: TestClient) -> None:
    """An empty instruction is a validation error."""
    created = post_document(client, CONTRACT)

    response = client.post(
        f"/documents/{created.document_id}/ai-redlines",
        json={"instruction": ""},
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
    assert response.json()["error_type"] == ErrorType.VALIDATION_ERROR


def post_document(client: TestClient, text: str) -> CreatedDocument:
    """Create a document and return its id and text."""
    request = CreateDocumentRequest(title=DOCUMENT_TITLE, text=text, author=DOCUMENT_AUTHOR)
    response = client.post("/documents", json=asdict(request))
    assert response.status_code == HTTPStatus.CREATED
    body = response.json()
    return CreatedDocument(document_id=body["id"], text=body["text"])


def post_redlines(client: TestClient, document_id: str, instruction: str) -> Response:
    """Request suggestions for one document."""
    request = AiRedlineRequest(instruction=instruction)
    return client.post(f"/documents/{document_id}/ai-redlines", json=asdict(request))


def install_model(client: TestClient, model_client: FakeModelClient | FailingModelClient) -> None:
    """Use this model client for the test."""

    def override() -> RedlineModelClient:
        """Return the test model client."""
        return model_client

    client.app.dependency_overrides[get_model_client] = override
