from dataclasses import asdict
from http import HTTPStatus

from fastapi.testclient import TestClient

from redline.api.schemas import (
    ApplyChangesRequest,
    ChangeRequest,
    ChangeTargetType,
    CreateDocumentRequest,
    OccurrenceTargetRequest,
)
from redline.editing.apply import apply_changes
from redline.editing.models import Change, OccurrenceTarget
from tests.fixtures.large_contract import LARGE_DOCUMENT_CHARACTER_COUNT, build_large_contract

SECTION_COUNT = 200
NEXT_VERSION = 2
DOCUMENT_TITLE = "Large contract"
DOCUMENT_AUTHOR = "Ada"


def test_large_document_round_trip_through_api(client: TestClient) -> None:
    """A 10MB document edited by section label matches the engine and version 2."""
    contract = build_large_contract(LARGE_DOCUMENT_CHARACTER_COUNT)
    changes = [
        Change(
            target=OccurrenceTarget(text=f"Section {number}.", occurrence=1),
            replacement=f"Clause {number}.",
        )
        for number in range(1, SECTION_COUNT + 1)
    ]
    expected = apply_changes(contract, changes).text
    created_request = CreateDocumentRequest(
        title=DOCUMENT_TITLE, text=contract, author=DOCUMENT_AUTHOR
    )
    created = client.post("/documents", json=asdict(created_request))
    created_body = created.json()
    patch_request = ApplyChangesRequest(
        author=DOCUMENT_AUTHOR,
        changes=[
            ChangeRequest(
                target=OccurrenceTargetRequest(
                    type=ChangeTargetType.OCCURRENCE,
                    text=f"Section {number}.",
                    occurrence=1,
                ),
                replacement=f"Clause {number}.",
            )
            for number in range(1, SECTION_COUNT + 1)
        ],
    )
    response = client.patch(
        f"/documents/{created_body['id']}",
        headers={"If-Match": f'"{created_body["id"]}-1"'},
        json=asdict(patch_request),
    )

    version_two = client.get(f"/documents/{created_body['id']}/versions/{NEXT_VERSION}")

    assert created.status_code == HTTPStatus.CREATED
    assert len(created_body["text"]) >= LARGE_DOCUMENT_CHARACTER_COUNT
    assert response.status_code == HTTPStatus.OK
    assert response.json()["document"]["text"] == expected
    assert version_two.json()["text"] == expected
