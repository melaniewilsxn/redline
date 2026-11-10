import pytest

from redline.editing.apply import apply_changes
from redline.editing.errors import OverlappingChangesError, TargetNotFoundError
from redline.editing.models import Change, ContextTarget, OccurrenceTarget, RangeTarget, TextSpan

DOCUMENT = "abcdefghij"


def test_single_replacement_returns_updated_text() -> None:
    """One range replacement rewrites only that span."""
    changes = [Change(target=RangeTarget(start=1, end=4), replacement="XYZ")]

    edited = apply_changes(DOCUMENT, changes)

    assert edited.text == "aXYZefghij"
    assert edited.applied_edits[0].span == TextSpan(start=1, end=4)


def test_changes_given_out_of_order_apply_by_position() -> None:
    """Changes apply from left to right, and applied edits keep the original offsets."""
    changes = [
        Change(target=RangeTarget(start=6, end=8), replacement="XY"),
        Change(target=RangeTarget(start=1, end=3), replacement="Q"),
    ]

    edited = apply_changes(DOCUMENT, changes)

    assert edited.text == "aQdefXYij"
    assert [edit.span for edit in edited.applied_edits] == [
        TextSpan(start=1, end=3),
        TextSpan(start=6, end=8),
    ]
    assert [edit.replacement_length for edit in edited.applied_edits] == [1, 2]


def test_empty_replacement_deletes() -> None:
    """An empty replacement removes the targeted text."""
    changes = [Change(target=RangeTarget(start=0, end=4), replacement="")]

    edited = apply_changes(DOCUMENT, changes)

    assert edited.text == "efghij"


def test_zero_width_change_inserts() -> None:
    """A zero-width range inserts the replacement at that point."""
    changes = [Change(target=RangeTarget(start=3, end=3), replacement="X")]

    edited = apply_changes(DOCUMENT, changes)

    assert edited.text == "abcXdefghij"


def test_mixed_target_types_apply_in_one_batch() -> None:
    """A range, an occurrence, and a context target apply together."""
    document = "alpha BRAVO charlie BRAVO delta"
    changes = [
        Change(target=RangeTarget(start=0, end=5), replacement="ALPHA"),
        Change(target=OccurrenceTarget(text="BRAVO", occurrence=2), replacement="bravo"),
        Change(
            target=ContextTarget(text="charlie", prefix="BRAVO ", suffix=" BRAVO"),
            replacement="CHARLIE",
        ),
    ]

    edited = apply_changes(document, changes)

    assert edited.text == "ALPHA BRAVO CHARLIE bravo delta"
    assert len(edited.applied_edits) == 3


def test_touching_ranges_both_apply() -> None:
    """Ranges that only meet at an edge both apply."""
    changes = [
        Change(target=RangeTarget(start=0, end=5), replacement="111"),
        Change(target=RangeTarget(start=5, end=9), replacement="2"),
    ]

    edited = apply_changes(DOCUMENT, changes)

    assert edited.text == "1112j"


def test_insert_at_start_of_replaced_range_goes_before_replacement() -> None:
    """An insert at the start of a replacement is placed before that replacement."""
    changes = [
        Change(target=RangeTarget(start=5, end=9), replacement="YZ"),
        Change(target=RangeTarget(start=5, end=5), replacement="X"),
    ]

    edited = apply_changes(DOCUMENT, changes)

    assert edited.text == "abcdeXYZj"


def test_insert_at_end_of_replaced_range_goes_after_replacement() -> None:
    """An insert at the end of a replacement is placed after that replacement."""
    changes = [
        Change(target=RangeTarget(start=9, end=9), replacement="X"),
        Change(target=RangeTarget(start=5, end=9), replacement="YZ"),
    ]

    edited = apply_changes(DOCUMENT, changes)

    assert edited.text == "abcdeYZXj"


def test_overlapping_ranges_raise_overlapping_changes_error() -> None:
    """Overlapping ranges are rejected using their request indexes."""
    changes = [
        Change(target=RangeTarget(start=5, end=9), replacement="RIGHT"),
        Change(target=RangeTarget(start=0, end=6), replacement="LEFT"),
    ]

    with pytest.raises(OverlappingChangesError) as raised:
        apply_changes(DOCUMENT, changes)

    assert raised.value.first_change_index == 1
    assert raised.value.second_change_index == 0


def test_insert_inside_replaced_range_raises_overlapping_changes_error() -> None:
    """An insert inside a replaced range overlaps that range."""
    changes = [
        Change(target=RangeTarget(start=5, end=9), replacement="YZ"),
        Change(target=RangeTarget(start=7, end=7), replacement="X"),
    ]

    with pytest.raises(OverlappingChangesError) as raised:
        apply_changes(DOCUMENT, changes)

    assert raised.value.first_change_index == 0
    assert raised.value.second_change_index == 1


def test_two_inserts_at_same_position_raise_overlapping_changes_error() -> None:
    """Two inserts at the same point overlap, because their order would be arbitrary."""
    changes = [
        Change(target=RangeTarget(start=5, end=5), replacement="A"),
        Change(target=RangeTarget(start=5, end=5), replacement="B"),
    ]

    with pytest.raises(OverlappingChangesError) as raised:
        apply_changes(DOCUMENT, changes)

    assert raised.value.first_change_index == 0
    assert raised.value.second_change_index == 1


def test_failing_target_rejects_whole_batch() -> None:
    """A missing target rejects the batch before any change is built."""
    changes = [
        Change(target=RangeTarget(start=0, end=1), replacement="A"),
        Change(target=OccurrenceTarget(text="missing", occurrence=1), replacement="B"),
        Change(target=RangeTarget(start=2, end=3), replacement="C"),
    ]

    with pytest.raises(TargetNotFoundError) as raised:
        apply_changes(DOCUMENT, changes)

    assert raised.value.change_index == 1


def test_empty_change_list_returns_original_text() -> None:
    """No changes leaves the text as it was."""
    edited = apply_changes(DOCUMENT, [])

    assert edited.text == DOCUMENT
    assert edited.applied_edits == []


def test_applied_edit_length_change_is_negative_for_shorter_replacement() -> None:
    """A shorter replacement reports a negative length change of the exact difference."""
    changes = [Change(target=RangeTarget(start=0, end=5), replacement="xy")]

    edited = apply_changes(DOCUMENT, changes)

    assert edited.applied_edits[0].length_change == -3


def test_applied_edit_length_change_is_positive_for_longer_replacement() -> None:
    """A longer replacement reports a positive length change of the exact difference."""
    changes = [Change(target=RangeTarget(start=0, end=2), replacement="abcdef")]

    edited = apply_changes(DOCUMENT, changes)

    assert edited.applied_edits[0].length_change == 4


def test_applied_edit_length_change_is_zero_for_same_length_replacement() -> None:
    """A same-length replacement reports a length change of zero."""
    changes = [Change(target=RangeTarget(start=0, end=3), replacement="abc")]

    edited = apply_changes(DOCUMENT, changes)

    assert edited.applied_edits[0].length_change == 0
