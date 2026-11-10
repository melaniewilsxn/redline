from dataclasses import dataclass
from enum import StrEnum

from redline.editing.models import TextSpan


class DroppedSuggestionReason(StrEnum):
    """Why a model suggestion could not be placed in the document."""

    EMPTY_TARGET = "empty_target"
    NO_CHANGE = "no_change"
    TARGET_NOT_FOUND = "target_not_found"
    AMBIGUOUS_TARGET = "ambiguous_target"
    OVERLAPS_EARLIER_SUGGESTION = "overlaps_earlier_suggestion"


@dataclass(frozen=True)
class PlaybookPosition:
    """One negotiating position."""

    topic: str
    preferred_position: str
    acceptable_fallbacks: list[str]
    never_accept: list[str]


@dataclass(frozen=True)
class Playbook:
    """The side we act for, and our positions."""

    represented_party: str
    positions: list[PlaybookPosition]


@dataclass(frozen=True)
class RedlineSuggestion:
    """One suggestion from the model, before it is checked against the document."""

    text: str
    prefix: str
    suffix: str
    replacement: str
    rationale: str
    title: str


@dataclass(frozen=True)
class AnchoredSuggestion:
    """A suggestion pinned to an exact span of the document."""

    suggestion_id: str
    span: TextSpan
    original_text: str
    replacement: str
    rationale: str
    title: str


@dataclass(frozen=True)
class DroppedSuggestion:
    """A suggestion that could not be placed, and why."""

    suggestion_id: str
    text: str
    replacement: str
    rationale: str
    title: str
    reason: DroppedSuggestionReason


@dataclass(frozen=True)
class AnchoredSuggestions:
    """The suggestions that anchored, and the ones that were dropped."""

    anchored: list[AnchoredSuggestion]
    dropped: list[DroppedSuggestion]
