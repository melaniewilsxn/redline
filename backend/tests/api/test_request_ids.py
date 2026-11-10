import logging

import pytest
from fastapi.testclient import TestClient

from redline.main import MAXIMUM_REQUEST_ID_LENGTH

GENERATED_REQUEST_ID_LENGTH = 32


def test_response_echoes_given_request_id(client: TestClient) -> None:
    """A short request id with no whitespace is echoed on the response."""
    response = client.get("/health", headers={"X-Request-ID": "reviewer-123"})

    assert response.headers["x-request-id"] == "reviewer-123"


def test_response_gets_generated_request_id_when_none_given(client: TestClient) -> None:
    """A request with no id gets a generated one."""
    response = client.get("/health")

    request_id = response.headers["x-request-id"]
    assert len(request_id) == GENERATED_REQUEST_ID_LENGTH
    assert all(character in "0123456789abcdef" for character in request_id)


def test_request_id_with_whitespace_is_replaced(client: TestClient) -> None:
    """A request id with whitespace is replaced."""
    response = client.get("/health", headers={"X-Request-ID": "bad id"})

    request_id = response.headers["x-request-id"]
    assert request_id != "bad id"
    assert not any(character.isspace() for character in request_id)


def test_request_id_over_maximum_length_is_replaced(client: TestClient) -> None:
    """A request id longer than the maximum is replaced."""
    supplied = "x" * (MAXIMUM_REQUEST_ID_LENGTH + 1)

    response = client.get("/health", headers={"X-Request-ID": supplied})

    assert response.headers["x-request-id"] != supplied
    assert len(response.headers["x-request-id"]) <= MAXIMUM_REQUEST_ID_LENGTH


def test_request_id_is_attached_to_log_records(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    """A log record written during the request carries that request id."""
    caplog.set_level(logging.INFO)
    request_id = "abc123"

    client.get("/health", headers={"X-Request-ID": request_id})

    matching = [
        record for record in caplog.records if getattr(record, "request_id", None) == request_id
    ]
    assert matching
