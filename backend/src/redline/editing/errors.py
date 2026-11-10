import logging
from enum import StrEnum

logger = logging.getLogger(__name__)


class InvalidTargetReason(StrEnum):
    """Why a target is malformed, whatever the document."""

    START_AFTER_END = "start_after_end"
    NEGATIVE_OFFSET = "negative_offset"
    OCCURRENCE_BELOW_ONE = "occurrence_below_one"
    EMPTY_OCCURRENCE_TEXT = "empty_occurrence_text"
    EMPTY_CONTEXT = "empty_context"
    UNKNOWN_TARGET_TYPE = "unknown_target_type"


class EditingError(Exception):
    """Base class for editing failures."""


class InvalidTargetError(EditingError):
    """A target is malformed for any document."""

    def __init__(self, change_index: int, reason: InvalidTargetReason) -> None:
        """Store the change index and the reason, and build a readable message."""
        self.change_index = change_index
        self.reason = reason
        super().__init__(f"Change {change_index + 1}: {describe_invalid_target(reason)}")


class RangeOutOfBoundsError(EditingError):
    """A range target ends past the end of the document."""

    def __init__(self, change_index: int, document_length: int) -> None:
        """Store the change index and the document length, and build a readable message."""
        self.change_index = change_index
        self.document_length = document_length
        super().__init__(
            f"Change {change_index + 1}: range ends past document length {document_length}"
        )


class TargetNotFoundError(EditingError):
    """No match exists, or the document has fewer occurrences than requested."""

    def __init__(self, change_index: int) -> None:
        """Store the change index and build a readable message."""
        self.change_index = change_index
        super().__init__(f"Change {change_index + 1}: text not found")


class AmbiguousTargetError(EditingError):
    """A context target matched more than once.

    match_count is at least two. Scanning stops at the second match, so the field does not
    hold the full total.
    """

    def __init__(self, change_index: int, match_count: int) -> None:
        """Store the change index and the match count, and build a readable message."""
        self.change_index = change_index
        self.match_count = match_count
        super().__init__(f"Change {change_index + 1}: target matched more than once")


class OverlappingChangesError(EditingError):
    """Two resolved changes cover the same character, or both insert at the same position.

    first_change_index is the left span. second_change_index is the right span. Both are
    positions in the request, counting from 0.
    """

    def __init__(self, first_change_index: int, second_change_index: int) -> None:
        """Store both request indexes and build a readable message."""
        self.first_change_index = first_change_index
        self.second_change_index = second_change_index
        super().__init__(
            f"Change {first_change_index + 1} overlaps change {second_change_index + 1}"
        )


def describe_invalid_target(reason: InvalidTargetReason) -> str:
    """Return a readable explanation of why a target is malformed."""
    match reason:
        case InvalidTargetReason.START_AFTER_END:
            return "start is after end"
        case InvalidTargetReason.NEGATIVE_OFFSET:
            return "offset is negative"
        case InvalidTargetReason.OCCURRENCE_BELOW_ONE:
            return "occurrence is below 1"
        case InvalidTargetReason.EMPTY_OCCURRENCE_TEXT:
            return "occurrence text is empty"
        case InvalidTargetReason.EMPTY_CONTEXT:
            return "context is empty"
        case InvalidTargetReason.UNKNOWN_TARGET_TYPE:
            return "target type is unknown"
        case _:
            logger.error(f"Unknown invalid target reason {reason}")
            return "target is invalid"
