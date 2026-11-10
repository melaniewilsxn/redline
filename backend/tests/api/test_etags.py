from uuid import UUID

import pytest

from redline.api.etags import PreconditionFailedError, build_etag, parse_if_match

DOCUMENT_ID = UUID("018f6b9c-7c3a-7000-8000-000000000001")
OTHER_DOCUMENT_ID = UUID("018f6b9c-7c3a-7000-8000-000000000002")
VERSION = 3


def test_build_etag_quotes_document_id_and_version() -> None:
    """An ETag is the quoted document id, a hyphen, and the version."""
    etag = build_etag(DOCUMENT_ID, VERSION)

    assert etag == f'"{DOCUMENT_ID}-{VERSION}"'


def test_parse_if_match_returns_version_for_matching_document() -> None:
    """A strong ETag for this document returns its version."""
    version = parse_if_match(build_etag(DOCUMENT_ID, VERSION), DOCUMENT_ID)

    assert version == VERSION


def test_parse_if_match_for_other_document_raises_precondition_failed_error() -> None:
    """An ETag for a different document is rejected."""
    with pytest.raises(PreconditionFailedError):
        parse_if_match(build_etag(OTHER_DOCUMENT_ID, VERSION), DOCUMENT_ID)


def test_parse_if_match_without_quotes_raises_precondition_failed_error() -> None:
    """An ETag without quotes is rejected."""
    with pytest.raises(PreconditionFailedError):
        parse_if_match(f"{DOCUMENT_ID}-{VERSION}", DOCUMENT_ID)


def test_parse_if_match_wildcard_raises_precondition_failed_error() -> None:
    """A wildcard If-Match is rejected."""
    with pytest.raises(PreconditionFailedError):
        parse_if_match("*", DOCUMENT_ID)


def test_parse_if_match_weak_etag_raises_precondition_failed_error() -> None:
    """A weak ETag is rejected."""
    with pytest.raises(PreconditionFailedError):
        parse_if_match(f"W/{build_etag(DOCUMENT_ID, VERSION)}", DOCUMENT_ID)


def test_parse_if_match_without_hyphen_raises_precondition_failed_error() -> None:
    """A quoted value with no version separator is rejected."""
    with pytest.raises(PreconditionFailedError):
        parse_if_match('"nohyphen"', DOCUMENT_ID)


def test_parse_if_match_with_non_decimal_version_raises_precondition_failed_error() -> None:
    """A version that is not a number is rejected."""
    with pytest.raises(PreconditionFailedError):
        parse_if_match(f'"{DOCUMENT_ID}-abc"', DOCUMENT_ID)


def test_parse_if_match_list_raises_precondition_failed_error() -> None:
    """A list of ETags is rejected."""
    etag_list = f"{build_etag(DOCUMENT_ID, VERSION)}, {build_etag(DOCUMENT_ID, VERSION + 1)}"

    with pytest.raises(PreconditionFailedError):
        parse_if_match(etag_list, DOCUMENT_ID)
