# Phase 1: Editing Engine

**Project:** Redline (see `docs/plans/build-plan.md`)
**Audience:** the coding agent building this phase

Read and follow the `code-guidelines` skill before writing any code. If this plan and the guidelines disagree, the guidelines win: follow them and tell the user what differed.

Code snippets in this plan are hints, not ground truth. Check each library's current documentation before using it. No long-running process needs to stay up during this phase.

## Goal

Build the pure editing engine in `backend/src/redline/editing/`. It resolves each change's target (a character range, text plus occurrence number, or text plus surrounding context) to an exact span. It applies a batch of changes atomically in one linear pass and rejects overlaps. It reports where each edit landed, so later phases can rebase proposals and re-index search. It also moves a span through a list of applied edits (rebase) and captures a span's surrounding context. Set up the backend tooling too: `pyproject.toml` with uv, Ruff, pytest, and a root `Makefile`. The phase ends with the unit tests and the 10MB tests passing.

The engine does no I/O. It imports nothing from `storage`, `services`, `api`, or any third-party package.

**Out of scope:** the database, the API and JSON schemas, `logging_setup.py` and request ids (phase 2), search, proposals as stored records (phase 4), and the benchmark script (phase 3).

## Files

```
redline/
├── Makefile                                  # section 1
└── backend/
    ├── .python-version                       # section 1 (new, created empty)
    ├── pyproject.toml                        # section 1
    ├── src/redline/editing/
    │   ├── models.py                         # section 2
    │   ├── errors.py                         # section 3
    │   ├── anchors.py                        # section 4
    │   ├── apply.py                          # section 5
    │   └── rebase.py                         # section 6
    └── tests/
        ├── fixtures/
        │   ├── __init__.py                   # empty (new)
        │   └── large_contract.py             # section 7 (new)
        ├── editing/
        │   ├── test_anchors.py               # section 8 (new)
        │   ├── test_apply.py                 # section 8 (new)
        │   └── test_rebase.py                # section 8 (new)
        └── large_documents/
            └── test_large_edits.py           # section 8 (new)
```

`__init__.py` files stay empty: no re-exports, no logic. Delete `backend/tests/fixtures/.gitkeep` once `__init__.py` exists there.

## 1. Tooling

### `backend/.python-version`

```
3.14
```

### `backend/pyproject.toml`

- `[project]`: name `redline`, version `0.1.0`, `requires-python = ">=3.14,<3.15"`, no runtime dependencies yet.
- `[build-system]`: `uv_build`, which defaults to the `src/redline/` layout.
- `[dependency-groups]` `dev`: `pytest~=9.2.0` and `ruff~=0.17.4`. Build backend requirement: `uv_build~=0.13.7` (uv requires an upper bound, and `~=` gives one). These were the latest on PyPI when this plan was reviewed.
- `[tool.ruff]`: `target-version = "py314"`, `line-length = 100`. `[tool.ruff.lint]` select `E`, `F`, `I`, `UP`, `B`, `N`, `SIM`, `RUF`. `[tool.ruff.format]` defaults.
- `[tool.pytest.ini_options]`: `testpaths = ["tests"]`, `addopts = "-ra"`. `tests/` is a package (it has `__init__.py`), so pytest puts `backend/` on the path and `from tests.fixtures.large_contract import ...` works. Check this, and if it does not, add `pythonpath = ["."]` and note why in a comment.

Imports are absolute from the package root: `from redline.editing.models import Change`.

### Root `Makefile`

Phase 1 targets only. Later phases add `dev`, `seed`, and `bench`.

| Target | Runs |
|---|---|
| `install` | `cd backend && uv sync` |
| `test` | `cd backend && uv run pytest` |
| `lint` | `cd backend && uv run ruff check . && uv run ruff format --check .` |
| `format` | `cd backend && uv run ruff format . && uv run ruff check --fix .` |

Declare all targets `.PHONY`.

## 2. `editing/models.py`

All dataclasses are `@dataclass(frozen=True)`. The engine never mutates its inputs.

```python
@dataclass(frozen=True)
class TextSpan:
    """A half-open [start, end) span of character offsets in a text."""
    start: int
    end: int

@dataclass(frozen=True)
class RangeTarget:
    """Targets text by its character offsets."""
    start: int
    end: int

@dataclass(frozen=True)
class OccurrenceTarget:
    """Targets the nth occurrence (counting from 1) of some exact text."""
    text: str
    occurrence: int

@dataclass(frozen=True)
class ContextTarget:
    """Targets exact text that sits directly between a prefix and a suffix."""
    text: str
    prefix: str
    suffix: str

ChangeTarget = RangeTarget | OccurrenceTarget | ContextTarget

@dataclass(frozen=True)
class Change:
    """One requested edit: what to target and what to put there."""
    target: ChangeTarget
    replacement: str

@dataclass(frozen=True)
class ResolvedChange:
    """A change pinned to an exact span. change_index is its position in the request."""
    change_index: int
    span: TextSpan
    replacement: str

@dataclass(frozen=True)
class AppliedEdit:
    """Where one edit landed, in offsets of the text before the batch."""
    span: TextSpan
    replacement_length: int

    @property
    def length_change(self) -> int:
        """Return how many characters the edit added (negative if it removed)."""

@dataclass(frozen=True)
class EditedText:
    """The text after a batch, and the edits applied, sorted by position."""
    text: str
    applied_edits: list[AppliedEdit]

@dataclass(frozen=True)
class SurroundingContext:
    """The text just before and just after a span."""
    prefix: str
    suffix: str

@dataclass(frozen=True)
class LiveSpan:
    """A span that survived a batch of edits, at its new position."""
    span: TextSpan

@dataclass(frozen=True)
class StaleSpan:
    """A span whose text was changed by an edit, so it can no longer be placed."""
    conflicting_edit: AppliedEdit

RebasedSpan = LiveSpan | StaleSpan
```

The engine targets have no `type` field. The JSON `type` field (`range`, `occurrence`, `context`) belongs to the API schemas in phase 2, which map onto these classes. The engine tells them apart with `match` on the class.

## 3. `editing/errors.py`

One base class and one subclass per failure, so the API in phase 2 can map each class to an `error_type` and a status code. Each takes its fields as required constructor arguments, stores them as attributes, and passes a readable message to `super().__init__`.

```python
class InvalidTargetReason(StrEnum):
    """Why a target is malformed, whatever the document."""
    START_AFTER_END = "start_after_end"
    NEGATIVE_OFFSET = "negative_offset"
    OCCURRENCE_BELOW_ONE = "occurrence_below_one"
    EMPTY_OCCURRENCE_TEXT = "empty_occurrence_text"
    EMPTY_CONTEXT = "empty_context"
    UNKNOWN_TARGET_TYPE = "unknown_target_type"
```

| Class | Fields | When | Phase 2 status |
|---|---|---|---|
| `EditingError(Exception)` | none | base class, never raised directly | — |
| `InvalidTarget` | `change_index: int`, `reason: InvalidTargetReason` | target is malformed whatever the document: start after end, a negative offset, occurrence below 1, empty text in an occurrence target, a context target whose text, prefix, and suffix are all empty, or a target class the engine does not know | 422 |
| `RangeOutOfBounds` | `change_index: int`, `document_length: int` | a range target ends past the end of the document | 422 |
| `TargetNotFound` | `change_index: int` | no match, or fewer occurrences than asked for | 422 |
| `AmbiguousTarget` | `change_index: int`, `match_count: int` | a context target matches more than once | 422 |
| `OverlappingChanges` | `first_change_index: int`, `second_change_index: int` | two resolved changes overlap (section 5) | 422 |

`change_index` is the 0-based position in the request's `changes` list, matching the JSON array. Messages count from 1 for people: `change_index == 0` reads `"Change 1: text not found"`. Phase 2 puts this message in the readable `error` field. Tests never assert on messages; they assert on classes, indexes, and `reason`.

## 4. `editing/anchors.py`

```python
CONTEXT_CHARACTER_COUNT = 32
```

| Function | One job |
|---|---|
| `resolve_change(text: str, change: Change, change_index: int) -> ResolvedChange` | Match on the target's class, call the matching resolver, and build the `ResolvedChange`. The `case _` fallback logs an error with the change index and the class name, then raises `InvalidTarget` with `UNKNOWN_TARGET_TYPE`. |
| `resolve_range_target(text: str, target: RangeTarget, change_index: int) -> TextSpan` | Check the range and return it as a span. |
| `resolve_occurrence_target(text: str, target: OccurrenceTarget, change_index: int) -> TextSpan` | Find the nth occurrence. |
| `resolve_context_target(text: str, target: ContextTarget, change_index: int) -> TextSpan` | Find the one place where prefix, text, and suffix appear together. |
| `get_surrounding_context(text: str, span: TextSpan) -> SurroundingContext` | Return up to `CONTEXT_CHARACTER_COUNT` characters on each side of the span, clipped at the document edges. |

Rules:

- **Range:** a negative start or end, or start after end, raises `InvalidTarget`. An end past `len(text)` raises `RangeOutOfBounds`. A zero-width range (start equals end) is valid and means insert. `start == end == len(text)` inserts at the end.
- **Occurrence:** `occurrence < 1` or empty `text` raises `InvalidTarget`. Count matches left to right without overlap: after a match, search again from the match's end, using `str.find` with a start position. So in `"aaaa"`, occurrence 2 of `"aa"` is `[2, 4)`, and occurrence 3 does not exist. Matching is case-sensitive. Stop scanning as soon as the nth match is found. Too few matches raises `TargetNotFound`.
- **Context:** if `text`, `prefix`, and `suffix` are all empty, raise `InvalidTarget`. Search for the whole string `prefix + text + suffix`. The span is `[match + len(prefix), match + len(prefix) + len(text))`. Count matches with overlap allowed (search again from `match + 1`), stopping at the second match. Zero matches raises `TargetNotFound`, and two or more raises `AmbiguousTarget` with `match_count=2` (the count stops at two, so the field means "at least two"; say so in its docstring). Empty `text` with a non-empty prefix or suffix is valid and gives a zero-width span between them: insert at an anchor. Empty prefix and suffix with non-empty text means the text must be unique in the document.
- Log a warning with the change index and target class at each raise. Do not log document text, which may be confidential.

`resolve_change` is the only function the rest of the engine calls. The three resolvers are public because the tests exercise them directly.

## 5. `editing/apply.py`

| Function | One job |
|---|---|
| `apply_changes(text: str, changes: list[Change]) -> EditedText` | Orchestrate: resolve every change (`resolve_change` with its list index), sort, check overlaps, rebuild, return the text and applied edits. |
| `raise_on_overlapping_changes(sorted_changes: list[ResolvedChange]) -> None` | Raise `OverlappingChanges` for the first overlapping neighbor pair. |
| `rebuild_text(text: str, sorted_changes: list[ResolvedChange]) -> str` | Build the new text in one pass. |

Rules:

- **Resolve everything first.** The first failing change raises before anything is built, so a batch applies completely or not at all.
- **Sort** with `sorted(resolved, key=lambda change: (change.span.start, change.span.end))`, inline in `apply_changes`. On equal keys `sorted` is stable, so request order breaks ties, and the overlap rule below rejects those ties anyway.
- **Overlap:** walk neighboring pairs `(previous, current)` in sorted order. They overlap if `current.span.start < previous.span.end`, or if both are zero-width at the same position. Checking only neighbors is enough: if a later change overlaps `previous`, so does every change sorted between them. Consequences, all intended:
  - `[0, 5)` then `[5, 9)`: they touch, and both apply.
  - an insert at 5 and a replace of `[5, 9)`: they sort as insert first, and both apply, so the inserted text comes before the replacement.
  - a replace of `[5, 9)` and an insert at 9: both apply, insert after.
  - an insert at 7 inside `[5, 9)`: overlap.
  - two inserts at 5: overlap.
- **Rebuild:** keep a cursor at 0. For each change in order, append `text[cursor:start]`, then the replacement, then move the cursor to `end`. Append `text[cursor:]` and `"".join` the pieces once. This is O(n + k) for n characters and k changes.
- `applied_edits` are built from the sorted changes, with spans in the original text's offsets.
- An empty `changes` list returns the original text and no edits. The API will require at least one change; the engine does not need to.
- **Logging:** `apply_changes` is on the critical journey. Log at entry (document length, change count) and at exit (new length, edit count). `logging.getLogger(__name__)`. No text content in logs.

## 6. `editing/rebase.py`

| Function | One job |
|---|---|
| `rebase_span(span: TextSpan, applied_edits: list[AppliedEdit]) -> RebasedSpan` | Move a span through one batch of applied edits, or report it stale. |

`applied_edits` is exactly `EditedText.applied_edits`: sorted, in the pre-batch offsets. The span is in those same offsets.

Rules, in this order, for each edit:

1. If `edit.span.end <= span.start`, the edit is wholly before the span: add `edit.length_change` to a running shift.
2. Else if `edit.span.start >= span.end`, the edit is wholly after: no effect.
3. Else they share a character: return `StaleSpan(conflicting_edit=edit)`.

Rule 1 is checked first, which settles the edge cases: an insert at the span's start shifts it; an insert at the span's end leaves it. For a zero-width span at `p`, an insert at `p` shifts it, an edit `[s, p)` shifts it, an edit `[p, e)` leaves it, and only an edit with `s < p < e` makes it stale.

If no edit conflicts, return `LiveSpan(TextSpan(span.start + shift, span.end + shift))`.

This is O(k) per span. Phase 4 calls it once per pending proposal, which is a few dozen at most, so a sweep over sorted spans isn't worth it. Note this in the design notes.

No logging here: it runs once per proposal, and the phase 4 service logs around the loop.

## 7. `tests/fixtures/large_contract.py`

```python
LARGE_DOCUMENT_CHARACTER_COUNT = 10 * 1024 * 1024
SECTION_TEMPLATE = (
    "Section {number}. Delivery. The Supplier shall deliver the Goods described in "
    "Schedule {number} to the Customer within thirty (30) days of the Order Date. "
    "The Customer may reject non-conforming Goods by written notice.\n\n"
)
```

`build_large_contract(minimum_character_count: int) -> str`: repeat `SECTION_TEMPLATE` with increasing section numbers starting at 1 until the text is at least `minimum_character_count` long. Build a list and join it once. Every section has unique text (its number), and the clause wording repeats, which is what the context target tests need.

Use a module-scoped pytest fixture in `test_large_edits.py` so the 10MB text is built once per module.

## 8. Tests

Set up, act, assert, with a blank line between the three parts. Assert on types, fields, and returned text, never on error messages. Use small literal texts in the unit tests, such as `"The Seller shall indemnify the Buyer. The Seller shall pay."`

### `tests/editing/test_anchors.py`

Range:
- `test_range_target_resolves_to_its_offsets`
- `test_zero_width_range_resolves_to_an_insert_point`
- `test_zero_width_range_at_document_end_is_valid`
- `test_range_ending_past_document_raises_range_out_of_bounds`
- `test_range_with_start_after_end_raises_invalid_target`
- `test_range_with_negative_start_raises_invalid_target` (the range also ends past the document, which proves the malformed check runs before the bounds check; assert `reason == NEGATIVE_OFFSET`)
- `test_range_with_negative_end_raises_invalid_target`

Occurrence:
- `test_first_occurrence_resolves`
- `test_later_occurrence_resolves`
- `test_occurrence_beyond_match_count_raises_target_not_found`
- `test_missing_text_raises_target_not_found`
- `test_occurrence_matching_is_case_sensitive` (`"seller"` does not find `"Seller"`)
- `test_occurrences_are_counted_without_overlap` (in `"aaaa"`: occurrence 2 of `"aa"` is `[2, 4)`, occurrence 3 raises)
- `test_occurrence_below_one_raises_invalid_target`
- `test_empty_occurrence_text_raises_invalid_target`

Context:
- `test_context_selects_the_matching_one_of_repeated_text` (`"The Seller"` appears twice; prefix and suffix pick the second)
- `test_context_matching_twice_raises_ambiguous_target` (check `match_count == 2`)
- `test_context_not_found_raises_target_not_found`
- `test_context_with_empty_prefix_and_suffix_resolves_unique_text`
- `test_context_with_empty_prefix_and_suffix_and_repeated_text_raises_ambiguous_target`
- `test_context_with_empty_text_resolves_insert_point_between_prefix_and_suffix`
- `test_context_with_all_fields_empty_raises_invalid_target`
- `test_context_matching_is_case_sensitive`
- `test_overlapping_context_matches_count_as_ambiguous` (`"aa"` with empty prefix and suffix in `"aaa"`: the matches at 0 and 1 overlap, so this only passes if the search resumes at `match + 1`)

Every `InvalidTarget` test asserts the expected `reason`.

Surrounding context:
- `test_surrounding_context_takes_context_length_on_each_side`
- `test_surrounding_context_is_clipped_at_document_start`
- `test_surrounding_context_is_clipped_at_document_end`
- `test_captured_context_resolves_back_to_the_same_span` (capture the context of the second `"The Seller"`, build a `ContextTarget`, and check it resolves to the same span)

Resolve change:
- `test_resolve_change_keeps_change_index_and_replacement`
- `test_unknown_target_class_raises_invalid_target` (pass an object of a class outside the union; assert `reason == UNKNOWN_TARGET_TYPE`)

### `tests/editing/test_apply.py`

- `test_single_replacement_returns_updated_text`
- `test_changes_given_out_of_order_apply_by_position` (also checks `applied_edits` are sorted and in pre-batch offsets)
- `test_empty_replacement_deletes`
- `test_zero_width_change_inserts`
- `test_mixed_target_types_apply_in_one_batch`
- `test_touching_ranges_both_apply`
- `test_insert_at_start_of_replaced_range_goes_before_replacement`
- `test_insert_at_end_of_replaced_range_goes_after_replacement`
- `test_overlapping_ranges_raise_overlapping_changes` (submit the right-hand span first, so `first_change_index == 1` for the left span and `second_change_index == 0` for the right one, proving the fields are request indexes, not sorted positions)
- `test_insert_inside_replaced_range_raises_overlapping_changes`
- `test_two_inserts_at_same_position_raise_overlapping_changes`
- `test_failing_target_rejects_whole_batch` (the second of three changes is missing: raises `TargetNotFound` with `change_index == 1`)
- `test_empty_change_list_returns_original_text`
- `test_applied_edit_length_change_is_negative_for_shorter_replacement`, `test_applied_edit_length_change_is_positive_for_longer_replacement`, and `test_applied_edit_length_change_is_zero_for_same_length_replacement`, each asserting the exact number

### `tests/editing/test_rebase.py`

Build `AppliedEdit` values directly; don't go through `apply_changes`.

- `test_longer_edit_before_span_shifts_it_right`
- `test_shorter_edit_before_span_shifts_it_left`
- `test_edit_after_span_leaves_it`
- `test_edit_overlapping_span_start_marks_it_stale`
- `test_edit_overlapping_span_end_marks_it_stale`
- `test_edit_inside_span_marks_it_stale`
- `test_edit_covering_span_marks_it_stale` (check `conflicting_edit` is that edit)
- `test_insert_at_span_start_shifts_it`
- `test_insert_at_span_end_leaves_it`
- `test_insert_at_zero_width_span_shifts_it`
- `test_edit_ending_at_zero_width_span_shifts_it`
- `test_edit_starting_at_zero_width_span_leaves_it`
- `test_edit_containing_zero_width_span_marks_it_stale`
- `test_several_edits_before_span_add_up`
- `test_edits_before_and_after_span_only_shift_by_those_before`
- `test_no_edits_leave_span_unchanged`

### `tests/large_documents/test_large_edits.py`

Write a reference implementation inside the test file: `apply_one_at_a_time(text, sorted_changes)`, which applies resolved changes from last to first with plain slicing. It's obviously correct, which makes it a good oracle.

- `test_thousand_range_changes_match_one_at_a_time_reference`: 1,000 non-overlapping range changes spread evenly over the 10MB text, with mixed replacement lengths (longer, shorter, empty, and zero-width inserts), given in shuffled order with a fixed `random.Random(seed)` seed. Assert the text equals the reference, and that `len(applied_edits) == 1000`.
- `test_occurrence_target_near_document_end_resolves`: target the unique `"Schedule {last_section_number} "` with occurrence 1, and check the span against `text.rfind`.
- `test_context_target_selects_one_repeated_clause`: the wording `"The Customer may reject"` repeats in every section. Use the prefix `"Schedule {n} to the Customer within thirty (30) days of the Order Date. "` for a section near the middle, and check the span.
- `test_spans_after_large_batch_rebase_to_the_same_text`: take five spans in parts of the document the batch doesn't touch, apply the 1,000-change batch, rebase the spans, and check that each `LiveSpan` covers the same characters in the new text as it did in the old.

Run these with the rest of the suite. Don't skip or mark them.

## 9. Design notes (for the README)

- **Why three target types.** Lawyers edit wording, not offsets. A range is exact but breaks when anything earlier changes. Occurrence numbers are easy to type but shift when a matching phrase is added above. Context (prefix and suffix, after the W3C TextQuoteSelector) survives most edits elsewhere and states intent: "this `Seller`, the one after `indemnify`".
- **Exact matching.** Anchors are case-sensitive and whitespace-exact, because in a contract "Seller" and "seller" can be different defined terms. Fuzzy matching would be a guess, and a wrong guess in a contract is worse than an error.
- **Atomic batches.** Every target resolves before any text is built, so a request applies completely or not at all. That is what a lawyer expects from one round of edits.
- **Linear rebuild.** Applying changes one at a time copies the whole document for each change, which is O(n × k). Sorting and joining slices once is O(n + k) (plus O(k log k) to sort). For the 10MB, 1,000-change test that is one pass instead of a thousand.
- **Resolution cost.** Each text target is a `str.find` scan, which is fast C code but still O(n) per target. So resolving is O(n × t), where t is the number of text-based targets, while range targets are O(1). For very large batches of text targets, a multi-pattern matcher such as Aho–Corasick (the `pyahocorasick` library) would find every target in one pass. That's a noted next step, not built now.
- **Offsets are pre-batch.** `AppliedEdit` positions refer to the text before the batch, which is the same frame the caller's ranges and pending proposals use. A single sweep can then rebase proposals and re-index search without replaying edits.
- **Rebase rules.** An edit that ends at or before a proposal moves it; one that starts at or after leaves it; any shared character makes it stale. Stale is honest: if someone rewrote the clause a proposal was editing, the proposal no longer means what its author meant.

## Checkpoints ✅

Stop at each checkpoint and report before going on.

1. **Tooling.** Run `make install` and `make lint`. Report the output of `cd backend && uv run python --version`, `uv run pytest --version`, and `uv run ruff --version`, and the pinned versions in `pyproject.toml`.
2. **Models and anchors.** Run `cd backend && uv run pytest tests/editing/test_anchors.py -v` and report the pass/fail list. Note anything in section 4 that was unclear or that you resolved differently.
3. **Apply and rebase.** Run `uv run pytest tests/editing -v` and report the list.
4. **Large documents.** Run `uv run pytest tests/large_documents -v --durations=5` and report the pass list and the five slowest durations.
5. **Final.** Run `make test` and `make lint`. Report the totals, and the output of `find backend/src/redline/editing backend/tests -name "*.py" -size +0`.

## Definition of done

- [ ] `backend/.python-version`, `pyproject.toml`, and the `Makefile` are in place. `make install`, `make test`, and `make lint` work from the repo root.
- [ ] `editing/` has `models.py`, `errors.py`, `anchors.py`, `apply.py`, and `rebase.py` as specified, with no third-party imports and no imports from other `redline` packages.
- [ ] Every function has a docstring and type hints. Constants are at the top of each file. `__init__.py` files are empty.
- [ ] `apply_changes` logs at entry and exit, the resolvers log a warning at each raise, and no log line contains document text.
- [ ] Every test named in section 8 exists and passes, including the 10MB tests, which run by default.
- [ ] `make lint` is clean.
- [ ] Each checkpoint was reported.
