import logging

from redline.editing.errors import (
    AmbiguousTargetError,
    InvalidTargetError,
    InvalidTargetReason,
    RangeOutOfBoundsError,
    TargetNotFoundError,
)
from redline.editing.models import (
    Change,
    ContextTarget,
    OccurrenceTarget,
    RangeTarget,
    ResolvedChange,
    SurroundingContext,
    TextSpan,
)

logger = logging.getLogger(__name__)

CONTEXT_CHARACTER_COUNT = 32
MINIMUM_OCCURRENCE = 1
AMBIGUOUS_MATCH_COUNT = 2


def resolve_change(text: str, change: Change, change_index: int) -> ResolvedChange:
    """Pin a change to an exact span."""
    target = change.target
    match target:
        case RangeTarget():
            span = resolve_range_target(text, target, change_index)
        case OccurrenceTarget():
            span = resolve_occurrence_target(text, target, change_index)
        case ContextTarget():
            span = resolve_context_target(text, target, change_index)
        case _:
            target_class = type(target).__name__
            logger.error(f"Unknown target class {target_class} for change {change_index}")
            raise InvalidTargetError(change_index, InvalidTargetReason.UNKNOWN_TARGET_TYPE)
    return ResolvedChange(
        change_index=change_index,
        span=span,
        replacement=change.replacement,
    )


def resolve_range_target(text: str, target: RangeTarget, change_index: int) -> TextSpan:
    """Return the range as a span, or reject it as malformed or out of bounds."""
    if target.start < 0 or target.end < 0:
        logger.warning(f"Rejected RangeTarget for change {change_index}, reason negative offset")
        raise InvalidTargetError(change_index, InvalidTargetReason.NEGATIVE_OFFSET)
    if target.start > target.end:
        logger.warning(f"Rejected RangeTarget for change {change_index}, reason start after end")
        raise InvalidTargetError(change_index, InvalidTargetReason.START_AFTER_END)
    if target.end > len(text):
        logger.warning(
            f"Rejected RangeTarget for change {change_index}, reason range out of bounds"
        )
        raise RangeOutOfBoundsError(change_index, len(text))
    return TextSpan(start=target.start, end=target.end)


def resolve_occurrence_target(text: str, target: OccurrenceTarget, change_index: int) -> TextSpan:
    """Find the nth non-overlapping occurrence of the target text."""
    if target.occurrence < MINIMUM_OCCURRENCE:
        logger.warning(
            f"Rejected OccurrenceTarget for change {change_index}, reason occurrence below 1"
        )
        raise InvalidTargetError(change_index, InvalidTargetReason.OCCURRENCE_BELOW_ONE)
    if target.text == "":
        logger.warning(
            f"Rejected OccurrenceTarget for change {change_index}, reason empty occurrence text"
        )
        raise InvalidTargetError(change_index, InvalidTargetReason.EMPTY_OCCURRENCE_TEXT)
    search_start = 0
    text_length = len(target.text)
    for _occurrence_index in range(target.occurrence):
        match_start = text.find(target.text, search_start)
        if match_start < 0:
            logger.warning(f"Rejected OccurrenceTarget for change {change_index}, target not found")
            raise TargetNotFoundError(change_index)
        search_start = match_start + text_length
    return TextSpan(start=match_start, end=match_start + text_length)


def resolve_context_target(text: str, target: ContextTarget, change_index: int) -> TextSpan:
    """Find the one span sitting directly between the prefix and the suffix."""
    if target.text == "" and target.prefix == "" and target.suffix == "":
        logger.warning(f"Rejected ContextTarget for change {change_index}, reason empty context")
        raise InvalidTargetError(change_index, InvalidTargetReason.EMPTY_CONTEXT)
    pattern = target.prefix + target.text + target.suffix
    first_match = text.find(pattern)
    if first_match < 0:
        logger.warning(f"Rejected ContextTarget for change {change_index}, target not found")
        raise TargetNotFoundError(change_index)
    second_match = text.find(pattern, first_match + 1)
    if second_match >= 0:
        logger.warning(f"Rejected ContextTarget for change {change_index}, target is ambiguous")
        raise AmbiguousTargetError(change_index, AMBIGUOUS_MATCH_COUNT)
    span_start = first_match + len(target.prefix)
    return TextSpan(start=span_start, end=span_start + len(target.text))


def get_surrounding_context(text: str, span: TextSpan) -> SurroundingContext:
    """Return up to CONTEXT_CHARACTER_COUNT characters on each side of the span."""
    prefix_start = max(span.start - CONTEXT_CHARACTER_COUNT, 0)
    suffix_end = min(span.end + CONTEXT_CHARACTER_COUNT, len(text))
    return SurroundingContext(
        prefix=text[prefix_start : span.start], suffix=text[span.end : suffix_end]
    )
