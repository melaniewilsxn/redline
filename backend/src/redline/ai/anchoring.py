import logging

from redline.ai.models import (
    AnchoredSuggestion,
    AnchoredSuggestions,
    DroppedSuggestion,
    DroppedSuggestionReason,
    RedlineSuggestion,
)
from redline.editing.anchors import resolve_context_target
from redline.editing.errors import AmbiguousTargetError, TargetNotFoundError
from redline.editing.models import ContextTarget, TextSpan

logger = logging.getLogger(__name__)

SUGGESTION_CHANGE_INDEX = 0


def anchor_suggestions(text: str, suggestions: list[RedlineSuggestion]) -> AnchoredSuggestions:
    """Pin each suggestion to the document, and drop the ones that do not resolve."""
    logger.info(
        f"Started anchoring {len(suggestions)} suggestions in a document of {len(text)} characters"
    )
    anchored: list[AnchoredSuggestion] = []
    dropped: list[DroppedSuggestion] = []
    for suggestion_index, suggestion in enumerate(suggestions):
        suggestion_id = f"s{suggestion_index + 1}"
        placed = place_suggestion(text, suggestion, suggestion_id)
        if isinstance(placed, DroppedSuggestion):
            dropped.append(placed)
            continue
        anchored.append(placed)
    kept, overlapping = drop_overlaps(anchored)
    dropped.extend(overlapping)
    log_anchor_result(kept, dropped)
    return AnchoredSuggestions(anchored=kept, dropped=dropped)


def place_suggestion(
    text: str, suggestion: RedlineSuggestion, suggestion_id: str
) -> AnchoredSuggestion | DroppedSuggestion:
    """Resolve one suggestion, or return it as dropped."""
    if suggestion.text == "":
        return DroppedSuggestion(
            suggestion_id=suggestion_id,
            text=suggestion.text,
            replacement=suggestion.replacement,
            rationale=suggestion.rationale,
            reason=DroppedSuggestionReason.EMPTY_TARGET,
        )
    if suggestion.replacement == suggestion.text:
        return DroppedSuggestion(
            suggestion_id=suggestion_id,
            text=suggestion.text,
            replacement=suggestion.replacement,
            rationale=suggestion.rationale,
            reason=DroppedSuggestionReason.NO_CHANGE,
        )
    try:
        span = resolve_quoted_text(text, suggestion)
    except TargetNotFoundError:
        return DroppedSuggestion(
            suggestion_id=suggestion_id,
            text=suggestion.text,
            replacement=suggestion.replacement,
            rationale=suggestion.rationale,
            reason=DroppedSuggestionReason.TARGET_NOT_FOUND,
        )
    except AmbiguousTargetError:
        return DroppedSuggestion(
            suggestion_id=suggestion_id,
            text=suggestion.text,
            replacement=suggestion.replacement,
            rationale=suggestion.rationale,
            reason=DroppedSuggestionReason.AMBIGUOUS_TARGET,
        )
    return AnchoredSuggestion(
        suggestion_id=suggestion_id,
        span=span,
        original_text=text[span.start : span.end],
        replacement=suggestion.replacement,
        rationale=suggestion.rationale,
    )


def resolve_quoted_text(text: str, suggestion: RedlineSuggestion) -> TextSpan:
    """Find the quote, retrying with the quote alone when the context misses."""
    try:
        return resolve_context_target(
            text,
            ContextTarget(text=suggestion.text, prefix=suggestion.prefix, suffix=suggestion.suffix),
            SUGGESTION_CHANGE_INDEX,
        )
    except TargetNotFoundError:
        return resolve_context_target(
            text,
            ContextTarget(text=suggestion.text, prefix="", suffix=""),
            SUGGESTION_CHANGE_INDEX,
        )


def drop_overlaps(
    anchored: list[AnchoredSuggestion],
) -> tuple[list[AnchoredSuggestion], list[DroppedSuggestion]]:
    """Keep non-overlapping suggestions. Spans that only touch both stay."""
    ordered = sorted(anchored, key=lambda suggestion: (suggestion.span.start, suggestion.span.end))
    kept: list[AnchoredSuggestion] = []
    dropped: list[DroppedSuggestion] = []
    for suggestion in ordered:
        if kept and suggestion.span.start < kept[-1].span.end:
            dropped.append(
                DroppedSuggestion(
                    suggestion_id=suggestion.suggestion_id,
                    text=suggestion.original_text,
                    replacement=suggestion.replacement,
                    rationale=suggestion.rationale,
                    reason=DroppedSuggestionReason.OVERLAPS_EARLIER_SUGGESTION,
                )
            )
            continue
        kept.append(suggestion)
    return kept, dropped


def log_anchor_result(anchored: list[AnchoredSuggestion], dropped: list[DroppedSuggestion]) -> None:
    """Log how many suggestions anchored and how many dropped, by reason."""
    reason_counts = [
        f"{reason.value} {sum(1 for item in dropped if item.reason == reason)}"
        for reason in DroppedSuggestionReason
    ]
    logger.info(
        f"Finished anchoring {len(anchored)} suggestions, dropped {len(dropped)} "
        f"({', '.join(reason_counts)})"
    )
