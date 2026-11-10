from redline.ai.anchoring import anchor_suggestions
from redline.ai.models import DroppedSuggestionReason, RedlineSuggestion
from redline.editing.apply import apply_changes
from redline.editing.models import Change, RangeTarget

INDEMNITY = "The Customer shall indemnify the Company."
RATIONALE = "The indemnity should be mutual."
TITLE = "Make the indemnity mutual"


def test_suggestion_with_exact_context_anchors() -> None:
    """A quote with the right prefix and suffix lands on that span."""
    quote = RedlineSuggestion(
        "indemnify the Company",
        "shall ",
        ".",
        "defend the Company",
        RATIONALE,
        TITLE,
    )

    anchored = anchor_suggestions(INDEMNITY, [quote])

    assert anchored.dropped == []
    assert len(anchored.anchored) == 1
    placed = anchored.anchored[0]
    assert placed.suggestion_id == "s1"
    assert placed.original_text == "indemnify the Company"
    assert INDEMNITY[placed.span.start : placed.span.end] == "indemnify the Company"
    assert placed.replacement == "defend the Company"


def test_suggestion_with_wrong_context_falls_back_to_unique_text() -> None:
    """A wrong prefix still anchors when the quote appears once."""
    quote = RedlineSuggestion(
        "indemnify the Company",
        "NOT THE PREFIX",
        "",
        "defend the Company",
        RATIONALE,
        TITLE,
    )

    anchored = anchor_suggestions(INDEMNITY, [quote])

    assert anchored.dropped == []
    assert anchored.anchored[0].original_text == "indemnify the Company"


def test_suggestion_with_wrong_context_and_repeated_text_is_dropped_as_ambiguous() -> None:
    """A wrong prefix and a repeated quote are dropped as ambiguous."""
    quote = RedlineSuggestion("Pay", "zzz", "", "Send", RATIONALE, TITLE)

    anchored = anchor_suggestions("Pay now. Pay later.", [quote])

    assert anchored.anchored == []
    assert anchored.dropped[0].reason == DroppedSuggestionReason.AMBIGUOUS_TARGET


def test_suggestion_with_ambiguous_context_is_dropped_as_ambiguous() -> None:
    """A prefix and suffix that match twice are dropped as ambiguous."""
    quote = RedlineSuggestion("Pay", "", " now", "Send", RATIONALE, TITLE)

    anchored = anchor_suggestions("Pay now. Pay now.", [quote])

    assert anchored.anchored == []
    assert anchored.dropped[0].reason == DroppedSuggestionReason.AMBIGUOUS_TARGET


def test_suggestion_with_missing_text_is_dropped_as_not_found() -> None:
    """A quote that is not in the document is dropped."""
    quote = RedlineSuggestion("not in the document", "", "", "gone", RATIONALE, TITLE)

    anchored = anchor_suggestions(INDEMNITY, [quote])

    assert anchored.anchored == []
    assert anchored.dropped[0].reason == DroppedSuggestionReason.TARGET_NOT_FOUND


def test_suggestion_with_empty_text_is_dropped() -> None:
    """An empty quote is dropped."""
    quote = RedlineSuggestion("", "", "", "inserted", RATIONALE, TITLE)

    anchored = anchor_suggestions(INDEMNITY, [quote])

    assert anchored.anchored == []
    assert anchored.dropped[0].reason == DroppedSuggestionReason.EMPTY_TARGET


def test_suggestion_without_change_is_dropped() -> None:
    """A replacement that copies the quote is dropped."""
    quote = RedlineSuggestion("indemnify", "shall ", " the", "indemnify", RATIONALE, TITLE)

    anchored = anchor_suggestions(INDEMNITY, [quote])

    assert anchored.anchored == []
    assert anchored.dropped[0].reason == DroppedSuggestionReason.NO_CHANGE


def test_overlapping_suggestion_is_dropped_and_earlier_one_kept() -> None:
    """The suggestion that starts first is kept when two spans overlap."""
    later = RedlineSuggestion("cdef", "", "", "XXXX", RATIONALE, TITLE)
    earlier = RedlineSuggestion("abcde", "", "", "YYYYY", RATIONALE, TITLE)

    anchored = anchor_suggestions("abcdefghij", [later, earlier])

    anchored_ids = [anchored_suggestion.suggestion_id for anchored_suggestion in anchored.anchored]
    assert anchored_ids == ["s2"]
    assert anchored.anchored[0].original_text == "abcde"
    assert anchored.dropped[0].suggestion_id == "s1"
    assert anchored.dropped[0].reason == DroppedSuggestionReason.OVERLAPS_EARLIER_SUGGESTION


def test_touching_suggestions_are_both_kept() -> None:
    """Spans that only touch are both kept."""
    later = RedlineSuggestion("fghij", "", "", "XXXXX", RATIONALE, TITLE)
    earlier = RedlineSuggestion("abcde", "", "", "YYYYY", RATIONALE, TITLE)

    anchored = anchor_suggestions("abcdefghij", [later, earlier])

    assert anchored.dropped == []
    anchored_text = [anchored_suggestion.original_text for anchored_suggestion in anchored.anchored]
    assert anchored_text == ["abcde", "fghij"]


def test_suggestion_ids_follow_model_order_after_sorting() -> None:
    """Ids follow the model's order even after the spans are sorted."""
    later = RedlineSuggestion("fghij", "", "", "XXXXX", RATIONALE, TITLE)
    earlier = RedlineSuggestion("abcde", "", "", "YYYYY", RATIONALE, TITLE)

    anchored = anchor_suggestions("abcdefghij", [later, earlier])

    anchored_ids = [anchored_suggestion.suggestion_id for anchored_suggestion in anchored.anchored]
    assert anchored_ids == ["s2", "s1"]


def test_anchored_suggestions_apply_as_one_batch() -> None:
    """Every anchored suggestion applies together as range changes."""
    text = "The Customer shall pay."
    quotes = [
        RedlineSuggestion("Customer", "The ", " shall", "Client", RATIONALE, TITLE),
        RedlineSuggestion("pay", "shall ", ".", "remit", RATIONALE, TITLE),
    ]

    anchored = anchor_suggestions(text, quotes)
    changes = [
        Change(
            target=RangeTarget(
                start=anchored_suggestion.span.start,
                end=anchored_suggestion.span.end,
            ),
            replacement=anchored_suggestion.replacement,
        )
        for anchored_suggestion in anchored.anchored
    ]
    edited = apply_changes(text, changes)

    assert anchored.dropped == []
    assert edited.text == "The Client shall remit."
