from dataclasses import dataclass
from uuid import UUID

from redline.editing.models import TextSpan


@dataclass(frozen=True)
class Token:
    """One normalized word and the characters it covers."""

    term: str
    span: TextSpan


@dataclass(frozen=True)
class TokenOccurrence:
    """A term's place in a chunk: token position and span relative to the chunk start."""

    position: int
    span: TextSpan


@dataclass(frozen=True)
class IndexedChunk:
    """One paragraph, with term positions relative to the chunk start."""

    start: int
    length: int
    token_count: int
    term_occurrences: dict[str, list[TokenOccurrence]]


@dataclass(frozen=True)
class SearchPhrase:
    """A quoted phrase, already normalized."""

    terms: list[str]


@dataclass(frozen=True)
class SearchQuery:
    """A parsed query. Terms are the unquoted words, in first-seen order."""

    terms: list[str]
    phrases: list[SearchPhrase]


@dataclass(frozen=True)
class AllDocuments:
    """Search every indexed document."""


@dataclass(frozen=True)
class SelectedDocuments:
    """Search only these documents."""

    document_ids: list[UUID]


SearchScope = AllDocuments | SelectedDocuments


@dataclass(frozen=True)
class Snippet:
    """A short excerpt. Offsets are absolute in the document."""

    span: TextSpan
    text: str
    highlights: list[TextSpan]


@dataclass(frozen=True)
class SearchHit:
    """One matching document."""

    document_id: UUID
    title: str
    version: int
    score: float
    match_count: int
    snippets: list[Snippet]


@dataclass(frozen=True)
class SearchPage:
    """One page of hits, plus how many documents matched before paging."""

    hits: list[SearchHit]
    total_count: int
