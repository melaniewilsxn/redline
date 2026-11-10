from dataclasses import dataclass


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
        return self.replacement_length - (self.span.end - self.span.start)


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
