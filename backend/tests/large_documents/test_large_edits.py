import random

import pytest

from redline.editing.anchors import (
    resolve_change,
    resolve_context_target,
    resolve_occurrence_target,
)
from redline.editing.apply import apply_changes
from redline.editing.models import (
    ContextTarget,
    LiveSpan,
    OccurrenceTarget,
    ResolvedChange,
    TextSpan,
)
from redline.editing.rebase import rebase_span
from tests.fixtures.large_contract import (
    CHANGE_COUNT,
    LARGE_DOCUMENT_CHARACTER_COUNT,
    build_large_contract,
    build_spread_changes,
)

CHANGE_ORDER_SEED = 1
GAP_OFFSET = 50
GAP_LENGTH = 20
UNTOUCHED_SPAN_INDEXES = (10, 200, 400, 600, 800)
REPEATED_CLAUSE = "The Customer may reject"
CLAUSE_PREFIX = "Schedule {number} to the Customer within thirty (30) days of the Order Date. "
CLAUSE_SUFFIX = " non-conforming Goods"


@pytest.fixture(scope="module")
def large_contract() -> str:
    """Build the 10MB contract once for every test in this module."""
    return build_large_contract(LARGE_DOCUMENT_CHARACTER_COUNT)


def apply_one_at_a_time(text: str, sorted_changes: list[ResolvedChange]) -> str:
    """Apply resolved changes from last to first, one slice at a time."""
    edited = text
    for change in reversed(sorted_changes):
        edited = edited[: change.span.start] + change.replacement + edited[change.span.end :]
    return edited


def get_section_number(section: str) -> int:
    """Return the section number from a clause that starts with 'Section N.'."""
    header = section.split(".", maxsplit=1)[0]
    return int(header.removeprefix("Section "))


def test_thousand_range_changes_match_one_at_a_time_reference(large_contract: str) -> None:
    """A thousand shuffled range changes match applying those changes from last to first."""
    assert len(large_contract) >= LARGE_DOCUMENT_CHARACTER_COUNT
    changes = build_spread_changes(len(large_contract))
    resolved = [
        resolve_change(large_contract, change, change_index)
        for change_index, change in enumerate(changes)
    ]
    sorted_changes = sorted(resolved, key=lambda change: (change.span.start, change.span.end))
    expected = apply_one_at_a_time(large_contract, sorted_changes)
    shuffled_changes = list(changes)
    random.Random(CHANGE_ORDER_SEED).shuffle(shuffled_changes)

    edited = apply_changes(large_contract, shuffled_changes)

    assert edited.text == expected
    assert len(edited.applied_edits) == CHANGE_COUNT


def test_occurrence_target_near_document_end_resolves(large_contract: str) -> None:
    """The unique schedule label in the last section resolves to that label."""
    last_section = large_contract.rstrip("\n").split("\n\n")[-1]
    section_number = get_section_number(last_section)
    needle = f"Schedule {section_number} "
    expected_start = large_contract.rfind(needle)

    span = resolve_occurrence_target(
        large_contract,
        OccurrenceTarget(text=needle, occurrence=1),
        0,
    )

    assert span == TextSpan(start=expected_start, end=expected_start + len(needle))


def test_context_target_selects_one_repeated_clause(large_contract: str) -> None:
    """A repeated clause is selected by the unique schedule sentence in front of it."""
    sections = large_contract.rstrip("\n").split("\n\n")
    section_number = get_section_number(sections[len(sections) // 2])
    prefix = CLAUSE_PREFIX.format(number=section_number)
    target = ContextTarget(text=REPEATED_CLAUSE, prefix=prefix, suffix=CLAUSE_SUFFIX)
    pattern_start = large_contract.find(prefix + REPEATED_CLAUSE + CLAUSE_SUFFIX)

    span = resolve_context_target(large_contract, target, 0)

    assert span == TextSpan(
        start=pattern_start + len(prefix),
        end=pattern_start + len(prefix) + len(REPEATED_CLAUSE),
    )


def test_spans_after_large_batch_rebase_to_the_same_text(large_contract: str) -> None:
    """Spans the batch does not touch cover the same characters after they are rebased."""
    stride = len(large_contract) // CHANGE_COUNT
    assert stride > GAP_OFFSET + GAP_LENGTH
    edited = apply_changes(large_contract, build_spread_changes(len(large_contract)))

    for index in UNTOUCHED_SPAN_INDEXES:
        start = index * stride + GAP_OFFSET
        span = TextSpan(start=start, end=start + GAP_LENGTH)
        original = large_contract[span.start : span.end]

        rebased = rebase_span(span, edited.applied_edits)

        assert isinstance(rebased, LiveSpan)
        assert edited.text[rebased.span.start : rebased.span.end] == original
