import logging
from typing import NoReturn
from uuid import UUID

logger = logging.getLogger(__name__)

ETAG_FORMAT = '"{document_id}-{version}"'
QUOTE = '"'


class PreconditionFailedError(Exception):
    """If-Match was sent and does not name this document's current version."""

    def __init__(self, if_match: str) -> None:
        """Store the header value and build a readable message."""
        self.if_match = if_match
        super().__init__("If-Match does not match this document")


class PreconditionRequiredError(Exception):
    """A write was sent without If-Match."""

    def __init__(self) -> None:
        """Build a readable message."""
        super().__init__("If-Match is required")


def build_etag(document_id: UUID, version: int) -> str:
    """Build a strong quoted ETag for a document version."""
    return ETAG_FORMAT.format(document_id=document_id, version=version)


def parse_if_match(if_match: str, document_id: UUID) -> int:
    """Return the version from a strong ETag for this document."""
    if not is_single_quoted_value(if_match):
        reject_if_match(document_id, if_match)
    body = if_match[1:-1]
    separator = body.rfind("-")
    if separator < 0:
        reject_if_match(document_id, if_match)
    try:
        parsed_document_id = UUID(body[:separator])
        version_text = body[separator + 1 :]
        if not version_text.isdecimal():
            raise ValueError
        version = int(version_text)
    except ValueError:
        reject_if_match(document_id, if_match)
    if parsed_document_id != document_id:
        logger.warning(
            f"Rejected If-Match naming document {parsed_document_id} for document {document_id}"
        )
        raise PreconditionFailedError(if_match)
    return version


def is_single_quoted_value(value: str) -> bool:
    """Return whether the whole value is one quoted string."""
    starts_and_ends_quoted = value.startswith(QUOTE) and value.endswith(QUOTE)
    return len(value) >= 2 and starts_and_ends_quoted and value.count(QUOTE) == 2


def reject_if_match(document_id: UUID, if_match: str) -> NoReturn:
    """Log a rejected If-Match and raise."""
    logger.warning(f"Rejected If-Match for document {document_id}")
    raise PreconditionFailedError(if_match)
