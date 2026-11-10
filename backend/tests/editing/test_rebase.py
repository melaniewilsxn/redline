from redline.editing.models import AppliedEdit, LiveSpan, StaleSpan, TextSpan
from redline.editing.rebase import rebase_span


def test_longer_edit_before_span_shifts_it_right() -> None:
    """An edit that adds characters before a span shifts the span right."""
    edit = AppliedEdit(span=TextSpan(start=0, end=4), replacement_length=8)
    span = TextSpan(start=10, end=14)

    rebased = rebase_span(span, [edit])

    assert isinstance(rebased, LiveSpan)
    assert rebased.span == TextSpan(start=14, end=18)


def test_shorter_edit_before_span_shifts_it_left() -> None:
    """An edit that removes characters before a span shifts the span left."""
    edit = AppliedEdit(span=TextSpan(start=0, end=6), replacement_length=2)
    span = TextSpan(start=10, end=14)

    rebased = rebase_span(span, [edit])

    assert isinstance(rebased, LiveSpan)
    assert rebased.span == TextSpan(start=6, end=10)


def test_edit_after_span_leaves_it() -> None:
    """An edit that starts at or after the span end leaves the span where it is."""
    edit = AppliedEdit(span=TextSpan(start=20, end=25), replacement_length=1)
    span = TextSpan(start=10, end=14)

    rebased = rebase_span(span, [edit])

    assert isinstance(rebased, LiveSpan)
    assert rebased.span == span


def test_edit_overlapping_span_start_marks_it_stale() -> None:
    """An edit that covers the start of a span makes that span stale."""
    edit = AppliedEdit(span=TextSpan(start=8, end=11), replacement_length=0)
    span = TextSpan(start=10, end=14)

    rebased = rebase_span(span, [edit])

    assert isinstance(rebased, StaleSpan)
    assert rebased.conflicting_edit is edit


def test_edit_overlapping_span_end_marks_it_stale() -> None:
    """An edit that covers the end of a span makes that span stale."""
    edit = AppliedEdit(span=TextSpan(start=12, end=16), replacement_length=0)
    span = TextSpan(start=10, end=14)

    rebased = rebase_span(span, [edit])

    assert isinstance(rebased, StaleSpan)
    assert rebased.conflicting_edit is edit


def test_edit_inside_span_marks_it_stale() -> None:
    """An edit inside a span makes that span stale."""
    edit = AppliedEdit(span=TextSpan(start=11, end=13), replacement_length=4)
    span = TextSpan(start=10, end=14)

    rebased = rebase_span(span, [edit])

    assert isinstance(rebased, StaleSpan)
    assert rebased.conflicting_edit is edit


def test_edit_covering_span_marks_it_stale() -> None:
    """An edit that covers a whole span makes that span stale."""
    edit = AppliedEdit(span=TextSpan(start=8, end=20), replacement_length=1)
    span = TextSpan(start=10, end=14)

    rebased = rebase_span(span, [edit])

    assert isinstance(rebased, StaleSpan)
    assert rebased.conflicting_edit is edit


def test_insert_at_span_start_shifts_it() -> None:
    """An insert at a span's start pushes the span to the right."""
    edit = AppliedEdit(span=TextSpan(start=10, end=10), replacement_length=3)
    span = TextSpan(start=10, end=14)

    rebased = rebase_span(span, [edit])

    assert isinstance(rebased, LiveSpan)
    assert rebased.span == TextSpan(start=13, end=17)


def test_insert_at_span_end_leaves_it() -> None:
    """An insert at a span's end stays outside the span."""
    edit = AppliedEdit(span=TextSpan(start=14, end=14), replacement_length=3)
    span = TextSpan(start=10, end=14)

    rebased = rebase_span(span, [edit])

    assert isinstance(rebased, LiveSpan)
    assert rebased.span == span


def test_insert_at_zero_width_span_shifts_it() -> None:
    """An insert at a zero-width span pushes that point to the right."""
    edit = AppliedEdit(span=TextSpan(start=10, end=10), replacement_length=2)
    span = TextSpan(start=10, end=10)

    rebased = rebase_span(span, [edit])

    assert isinstance(rebased, LiveSpan)
    assert rebased.span == TextSpan(start=12, end=12)


def test_edit_ending_at_zero_width_span_shifts_it() -> None:
    """An edit that ends on a zero-width span is wholly before that point."""
    edit = AppliedEdit(span=TextSpan(start=6, end=10), replacement_length=1)
    span = TextSpan(start=10, end=10)

    rebased = rebase_span(span, [edit])

    assert isinstance(rebased, LiveSpan)
    assert rebased.span == TextSpan(start=7, end=7)


def test_edit_starting_at_zero_width_span_leaves_it() -> None:
    """An edit that starts on a zero-width span is wholly after that point."""
    edit = AppliedEdit(span=TextSpan(start=10, end=15), replacement_length=9)
    span = TextSpan(start=10, end=10)

    rebased = rebase_span(span, [edit])

    assert isinstance(rebased, LiveSpan)
    assert rebased.span == span


def test_edit_containing_zero_width_span_marks_it_stale() -> None:
    """An edit that extends on both sides of a zero-width span makes it stale."""
    edit = AppliedEdit(span=TextSpan(start=8, end=12), replacement_length=0)
    span = TextSpan(start=10, end=10)

    rebased = rebase_span(span, [edit])

    assert isinstance(rebased, StaleSpan)
    assert rebased.conflicting_edit is edit


def test_several_edits_before_span_add_up() -> None:
    """Length changes from every edit before a span are added together."""
    edits = [
        AppliedEdit(span=TextSpan(start=0, end=2), replacement_length=5),
        AppliedEdit(span=TextSpan(start=4, end=5), replacement_length=0),
    ]
    span = TextSpan(start=10, end=12)

    rebased = rebase_span(span, edits)

    assert isinstance(rebased, LiveSpan)
    assert rebased.span == TextSpan(start=12, end=14)


def test_edits_before_and_after_span_only_shift_by_those_before() -> None:
    """Edits after a span do not change how far it moves."""
    edits = [
        AppliedEdit(span=TextSpan(start=0, end=3), replacement_length=6),
        AppliedEdit(span=TextSpan(start=20, end=22), replacement_length=0),
    ]
    span = TextSpan(start=10, end=12)

    rebased = rebase_span(span, edits)

    assert isinstance(rebased, LiveSpan)
    assert rebased.span == TextSpan(start=13, end=15)


def test_no_edits_leave_span_unchanged() -> None:
    """A span with no edits stays at its original offsets."""
    span = TextSpan(start=10, end=14)

    rebased = rebase_span(span, [])

    assert isinstance(rebased, LiveSpan)
    assert rebased.span == span
