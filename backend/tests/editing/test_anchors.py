import pytest

from redline.editing.anchors import (
    CONTEXT_CHARACTER_COUNT,
    get_surrounding_context,
    resolve_change,
    resolve_context_target,
    resolve_occurrence_target,
    resolve_range_target,
)
from redline.editing.errors import (
    AmbiguousTargetError,
    InvalidTargetError,
    InvalidTargetReason,
    RangeOutOfBoundsError,
    TargetNotFoundError,
)
from redline.editing.models import Change, ContextTarget, OccurrenceTarget, RangeTarget, TextSpan

CONTRACT_TEXT = "The Seller shall indemnify the Buyer. The Seller shall pay."
SELLER = "The Seller"


class UnsupportedTarget:
    """A target class the editing engine does not resolve."""


def test_range_target_resolves_to_its_offsets() -> None:
    """A range target resolves to the offsets it names."""
    document = "abcdefghij"
    target = RangeTarget(start=2, end=6)

    span = resolve_range_target(document, target, 0)

    assert span == TextSpan(start=2, end=6)


def test_zero_width_range_resolves_to_an_insert_point() -> None:
    """A range whose start equals its end is an insert point."""
    document = "abcdefghij"
    target = RangeTarget(start=3, end=3)

    span = resolve_range_target(document, target, 0)

    assert span == TextSpan(start=3, end=3)


def test_zero_width_range_at_document_end_is_valid() -> None:
    """An insert at the document length is inside the document."""
    document = "abc"
    target = RangeTarget(start=3, end=3)

    span = resolve_range_target(document, target, 0)

    assert span == TextSpan(start=3, end=3)


def test_range_ending_past_document_raises_range_out_of_bounds_error() -> None:
    """A range that ends past the document is out of bounds."""
    document = "hello"
    target = RangeTarget(start=0, end=6)

    with pytest.raises(RangeOutOfBoundsError) as raised:
        resolve_range_target(document, target, 2)

    assert raised.value.change_index == 2
    assert raised.value.document_length == len(document)


def test_range_with_start_after_end_raises_invalid_target_error() -> None:
    """A range whose start is after its end is malformed."""
    document = "abcdefghij"
    target = RangeTarget(start=4, end=1)

    with pytest.raises(InvalidTargetError) as raised:
        resolve_range_target(document, target, 0)

    assert raised.value.change_index == 0
    assert raised.value.reason is InvalidTargetReason.START_AFTER_END


def test_range_with_negative_start_raises_invalid_target_error() -> None:
    """A negative start is invalid even when the end is also past the document."""
    document = "hello"
    target = RangeTarget(start=-1, end=100)

    with pytest.raises(InvalidTargetError) as raised:
        resolve_range_target(document, target, 0)

    assert raised.value.change_index == 0
    assert raised.value.reason is InvalidTargetReason.NEGATIVE_OFFSET


def test_range_with_negative_end_raises_invalid_target_error() -> None:
    """A negative end is invalid even when it is also before the start."""
    document = "abcdefghij"
    target = RangeTarget(start=2, end=-1)

    with pytest.raises(InvalidTargetError) as raised:
        resolve_range_target(document, target, 3)

    assert raised.value.change_index == 3
    assert raised.value.reason is InvalidTargetReason.NEGATIVE_OFFSET


def test_first_occurrence_resolves() -> None:
    """Occurrence 1 is the first exact match."""
    target = OccurrenceTarget(text="Seller", occurrence=1)
    expected_start = CONTRACT_TEXT.index("Seller")

    span = resolve_occurrence_target(CONTRACT_TEXT, target, 0)

    assert span == TextSpan(start=expected_start, end=expected_start + len("Seller"))


def test_later_occurrence_resolves() -> None:
    """A later occurrence skips the earlier exact matches."""
    target = OccurrenceTarget(text="Seller", occurrence=2)
    expected_start = CONTRACT_TEXT.index("Seller", CONTRACT_TEXT.index("Seller") + 1)

    span = resolve_occurrence_target(CONTRACT_TEXT, target, 0)

    assert span == TextSpan(start=expected_start, end=expected_start + len("Seller"))


def test_occurrence_beyond_match_count_raises_target_not_found_error() -> None:
    """Asking for more occurrences than exist does not resolve."""
    target = OccurrenceTarget(text="Seller", occurrence=3)

    with pytest.raises(TargetNotFoundError) as raised:
        resolve_occurrence_target(CONTRACT_TEXT, target, 1)

    assert raised.value.change_index == 1


def test_missing_text_raises_target_not_found_error() -> None:
    """Text that never occurs does not resolve."""
    target = OccurrenceTarget(text="Witness", occurrence=1)

    with pytest.raises(TargetNotFoundError) as raised:
        resolve_occurrence_target(CONTRACT_TEXT, target, 0)

    assert raised.value.change_index == 0


def test_occurrence_matching_is_case_sensitive() -> None:
    """A lowercase search does not match a capitalized word."""
    target = OccurrenceTarget(text="seller", occurrence=1)

    with pytest.raises(TargetNotFoundError) as raised:
        resolve_occurrence_target(CONTRACT_TEXT, target, 0)

    assert raised.value.change_index == 0


def test_occurrences_are_counted_without_overlap() -> None:
    """The next search starts at the end of the previous match."""
    document = "aaaa"
    second = OccurrenceTarget(text="aa", occurrence=2)
    third = OccurrenceTarget(text="aa", occurrence=3)

    span = resolve_occurrence_target(document, second, 0)

    assert span == TextSpan(start=2, end=4)

    with pytest.raises(TargetNotFoundError) as raised:
        resolve_occurrence_target(document, third, 4)

    assert raised.value.change_index == 4


def test_occurrence_below_one_raises_invalid_target_error() -> None:
    """Occurrence numbers start at 1."""
    target = OccurrenceTarget(text="Seller", occurrence=0)

    with pytest.raises(InvalidTargetError) as raised:
        resolve_occurrence_target(CONTRACT_TEXT, target, 0)

    assert raised.value.change_index == 0
    assert raised.value.reason is InvalidTargetReason.OCCURRENCE_BELOW_ONE


def test_empty_occurrence_text_raises_invalid_target_error() -> None:
    """An empty occurrence string is malformed."""
    target = OccurrenceTarget(text="", occurrence=1)

    with pytest.raises(InvalidTargetError) as raised:
        resolve_occurrence_target(CONTRACT_TEXT, target, 0)

    assert raised.value.change_index == 0
    assert raised.value.reason is InvalidTargetReason.EMPTY_OCCURRENCE_TEXT


def test_context_selects_the_matching_one_of_repeated_text() -> None:
    """Prefix and suffix select the second copy of repeated text."""
    target = ContextTarget(text=SELLER, prefix="Buyer. ", suffix=" shall pay.")
    expected_start = CONTRACT_TEXT.index(SELLER, 1)

    span = resolve_context_target(CONTRACT_TEXT, target, 0)

    assert span == TextSpan(start=expected_start, end=expected_start + len(SELLER))


def test_context_matching_twice_raises_ambiguous_target_error() -> None:
    """A context pattern that appears twice is ambiguous."""
    document = "[[go]] [[go]]"
    target = ContextTarget(text="go", prefix="[[", suffix="]]")

    with pytest.raises(AmbiguousTargetError) as raised:
        resolve_context_target(document, target, 5)

    assert raised.value.change_index == 5
    assert raised.value.match_count == 2


def test_context_not_found_raises_target_not_found_error() -> None:
    """A context pattern that never appears does not resolve."""
    target = ContextTarget(text="not present", prefix="xx", suffix="yy")

    with pytest.raises(TargetNotFoundError) as raised:
        resolve_context_target(CONTRACT_TEXT, target, 0)

    assert raised.value.change_index == 0


def test_context_with_empty_prefix_and_suffix_resolves_unique_text() -> None:
    """Unique text with an empty prefix and suffix resolves to that text."""
    target = ContextTarget(text="indemnify", prefix="", suffix="")
    expected_start = CONTRACT_TEXT.index("indemnify")

    span = resolve_context_target(CONTRACT_TEXT, target, 0)

    assert span == TextSpan(start=expected_start, end=expected_start + len("indemnify"))


def test_context_with_empty_prefix_and_suffix_and_repeated_text_raises_ambiguous_target_error() -> (
    None
):
    """Repeated text with an empty prefix and suffix is ambiguous."""
    target = ContextTarget(text="Seller", prefix="", suffix="")

    with pytest.raises(AmbiguousTargetError) as raised:
        resolve_context_target(CONTRACT_TEXT, target, 0)

    assert raised.value.change_index == 0
    assert raised.value.match_count == 2


def test_context_with_empty_text_resolves_insert_point_between_prefix_and_suffix() -> None:
    """Empty text between a prefix and a suffix is an insert point."""
    target = ContextTarget(text="", prefix="Buyer. ", suffix="The")
    pattern = "Buyer. The"
    expected_start = CONTRACT_TEXT.index(pattern) + len("Buyer. ")

    span = resolve_context_target(CONTRACT_TEXT, target, 0)

    assert span == TextSpan(start=expected_start, end=expected_start)


def test_context_with_all_fields_empty_raises_invalid_target_error() -> None:
    """A context target with nothing to search for is malformed."""
    target = ContextTarget(text="", prefix="", suffix="")

    with pytest.raises(InvalidTargetError) as raised:
        resolve_context_target(CONTRACT_TEXT, target, 0)

    assert raised.value.change_index == 0
    assert raised.value.reason is InvalidTargetReason.EMPTY_CONTEXT


def test_context_matching_is_case_sensitive() -> None:
    """Context text must match the document's capitalization."""
    target = ContextTarget(text="seller", prefix="", suffix="")

    with pytest.raises(TargetNotFoundError) as raised:
        resolve_context_target(CONTRACT_TEXT, target, 0)

    assert raised.value.change_index == 0


def test_overlapping_context_matches_count_as_ambiguous() -> None:
    """Overlapping matches count separately, so the search resumes one character later."""
    target = ContextTarget(text="aa", prefix="", suffix="")

    with pytest.raises(AmbiguousTargetError) as raised:
        resolve_context_target("aaa", target, 0)

    assert raised.value.change_index == 0
    assert raised.value.match_count == 2


def test_surrounding_context_takes_context_length_on_each_side() -> None:
    """Each side keeps CONTEXT_CHARACTER_COUNT characters when more are available."""
    left = "a" * (CONTEXT_CHARACTER_COUNT + 5)
    right = "b" * (CONTEXT_CHARACTER_COUNT + 5)
    document = left + "TARGET" + right
    span = TextSpan(start=len(left), end=len(left) + len("TARGET"))

    context = get_surrounding_context(document, span)

    assert context.prefix == left[-CONTEXT_CHARACTER_COUNT:]
    assert context.suffix == right[:CONTEXT_CHARACTER_COUNT]


def test_surrounding_context_is_clipped_at_document_start() -> None:
    """The prefix stops at the start of the document."""
    document = "abcTARGET"
    span = TextSpan(start=3, end=9)

    context = get_surrounding_context(document, span)

    assert context.prefix == "abc"
    assert context.suffix == ""


def test_surrounding_context_is_clipped_at_document_end() -> None:
    """The suffix stops at the end of the document."""
    document = "TARGETabc"
    span = TextSpan(start=0, end=6)

    context = get_surrounding_context(document, span)

    assert context.prefix == ""
    assert context.suffix == "abc"


def test_captured_context_resolves_back_to_the_same_span() -> None:
    """Context captured around the second Seller resolves back to that span."""
    expected_start = CONTRACT_TEXT.index(SELLER, 1)
    span = TextSpan(start=expected_start, end=expected_start + len(SELLER))
    context = get_surrounding_context(CONTRACT_TEXT, span)
    target = ContextTarget(text=SELLER, prefix=context.prefix, suffix=context.suffix)

    resolved = resolve_context_target(CONTRACT_TEXT, target, 0)

    assert resolved == span


def test_resolve_change_keeps_change_index_and_replacement() -> None:
    """Resolving a change keeps its request index and replacement."""
    change = Change(target=RangeTarget(start=0, end=3), replacement="A")

    resolved = resolve_change(CONTRACT_TEXT, change, 4)

    assert resolved.change_index == 4
    assert resolved.replacement == "A"
    assert resolved.span == TextSpan(start=0, end=3)


def test_unknown_target_class_raises_invalid_target_error() -> None:
    """A target class outside the three known classes is rejected."""
    change = Change(target=UnsupportedTarget(), replacement="x")

    with pytest.raises(InvalidTargetError) as raised:
        resolve_change(CONTRACT_TEXT, change, 6)

    assert raised.value.change_index == 6
    assert raised.value.reason is InvalidTargetReason.UNKNOWN_TARGET_TYPE
