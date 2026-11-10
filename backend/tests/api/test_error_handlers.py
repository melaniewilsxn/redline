from http import HTTPStatus

from fastapi.exceptions import RequestValidationError

from redline.api.error_handlers import (
    INVALID_REQUEST_SUMMARY,
    UNKNOWN_STATUS_PHRASE,
    VALIDATION_ERROR_KIND,
    VALIDATION_LOCATION,
    get_reason_phrase,
    get_validation_summary,
)

UNKNOWN_STATUS_CODE = 999


def test_get_validation_summary_without_details_is_generic() -> None:
    """A validation error with no details uses the generic summary."""
    error = RequestValidationError([])

    summary = get_validation_summary(error)

    assert summary.location == VALIDATION_LOCATION
    assert summary.error_kind == VALIDATION_ERROR_KIND
    assert summary.summary == INVALID_REQUEST_SUMMARY


def test_get_validation_summary_with_missing_keys_is_generic() -> None:
    """A validation detail without loc, msg, and type uses the generic summary."""
    error = RequestValidationError([{"type": "value_error"}])

    summary = get_validation_summary(error)

    assert summary.location == VALIDATION_LOCATION
    assert summary.error_kind == VALIDATION_ERROR_KIND
    assert summary.summary == INVALID_REQUEST_SUMMARY


def test_get_validation_summary_uses_the_first_detail() -> None:
    """A complete validation detail is summarized from its location and message."""
    error = RequestValidationError(
        [{"loc": ("body", "title"), "msg": "Field required", "type": "missing"}]
    )

    summary = get_validation_summary(error)

    assert summary.location == "body.title"
    assert summary.error_kind == "missing"
    assert summary.summary == "body.title: Field required"


def test_get_reason_phrase_returns_the_standard_phrase() -> None:
    """A known status returns its standard reason phrase."""
    phrase = get_reason_phrase(HTTPStatus.NOT_FOUND)

    assert phrase == HTTPStatus.NOT_FOUND.phrase


def test_get_reason_phrase_unknown_status_returns_the_fallback() -> None:
    """An unknown status returns the fallback phrase."""
    phrase = get_reason_phrase(UNKNOWN_STATUS_CODE)

    assert phrase == UNKNOWN_STATUS_PHRASE
