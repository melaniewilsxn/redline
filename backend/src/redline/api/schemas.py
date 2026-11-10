import logging
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field

from redline.ai.models import DroppedSuggestionReason
from redline.editing.errors import InvalidTargetError, InvalidTargetReason
from redline.editing.models import Change, ContextTarget, OccurrenceTarget, RangeTarget

logger = logging.getLogger(__name__)

MINIMUM_PAGE_LIMIT = 1
MAXIMUM_PAGE_LIMIT = 100
DEFAULT_PAGE_LIMIT = 20
MINIMUM_PAGE_OFFSET = 0


class ErrorType(StrEnum):
    """Stable code for an API error."""

    VALIDATION_ERROR = "validation_error"
    INVALID_QUERY = "invalid_query"
    INVALID_TARGET = "invalid_target"
    RANGE_OUT_OF_BOUNDS = "range_out_of_bounds"
    TARGET_NOT_FOUND = "target_not_found"
    AMBIGUOUS_TARGET = "ambiguous_target"
    OVERLAPPING_CHANGES = "overlapping_changes"
    DOCUMENT_NOT_FOUND = "document_not_found"
    VERSION_NOT_FOUND = "version_not_found"
    PRECONDITION_FAILED = "precondition_failed"
    PRECONDITION_REQUIRED = "precondition_required"
    AI_NOT_CONFIGURED = "ai_not_configured"
    MODEL_UNAVAILABLE = "model_unavailable"
    MODEL_RESPONSE_INVALID = "model_response_invalid"
    HTTP_ERROR = "http_error"
    INTERNAL_ERROR = "internal_error"


class ChangeTargetType(StrEnum):
    """How a change points at text."""

    RANGE = "range"
    OCCURRENCE = "occurrence"
    CONTEXT = "context"


@dataclass
class RangeTargetRequest:
    """A change that points at a character range."""

    type: Literal[ChangeTargetType.RANGE]
    start: int
    end: int


@dataclass
class OccurrenceTargetRequest:
    """A change that points at the nth exact match."""

    type: Literal[ChangeTargetType.OCCURRENCE]
    text: str
    occurrence: int


@dataclass
class ContextTargetRequest:
    """A change that points at exact text between a prefix and a suffix."""

    type: Literal[ChangeTargetType.CONTEXT]
    text: str
    prefix: str
    suffix: str


TargetRequest = Annotated[
    RangeTargetRequest | OccurrenceTargetRequest | ContextTargetRequest,
    Field(discriminator="type"),
]


@dataclass
class ChangeRequest:
    """One change: the text to replace and what to put there."""

    target: TargetRequest
    replacement: str


@dataclass
class ApplyChangesRequest:
    """A batch of changes to apply to one document."""

    author: Annotated[str, Field(min_length=1)]
    changes: Annotated[list[ChangeRequest], Field(min_length=1)]


@dataclass
class CreateDocumentRequest:
    """The title, text, and author for a new document."""

    title: Annotated[str, Field(min_length=1)]
    text: str
    author: Annotated[str, Field(min_length=1)]


@dataclass
class DocumentResponse:
    """A document and its current text."""

    id: UUID
    title: str
    version: int
    text: str
    created_at: datetime
    updated_at: datetime


@dataclass
class AppliedEditResponse:
    """Where one edit landed, in offsets from before the batch."""

    start: int
    end: int
    replacement_length: int


@dataclass
class ApplyChangesResponse:
    """The document after a batch, and where each edit landed."""

    document: DocumentResponse
    applied_edits: list[AppliedEditResponse]


@dataclass
class DocumentSummaryResponse:
    """A document without its text."""

    id: UUID
    title: str
    version: int
    character_count: int
    updated_at: datetime


@dataclass
class DocumentListResponse:
    """One page of documents."""

    documents: list[DocumentSummaryResponse]
    total_count: int
    limit: int
    offset: int


@dataclass
class VersionSummaryResponse:
    """One saved version without its text."""

    version: int
    author: str
    summary: str
    character_count: int
    created_at: datetime


@dataclass
class DocumentVersionResponse:
    """One saved version, including its text."""

    document_id: UUID
    version: int
    text: str
    author: str
    summary: str
    created_at: datetime


@dataclass
class TextSpanResponse:
    """A character span in a document."""

    start: int
    end: int


@dataclass
class SnippetResponse:
    """A short excerpt and the spans that matched."""

    start: int
    end: int
    text: str
    highlights: list[TextSpanResponse]


@dataclass
class SearchHitResponse:
    """One document that matched a search."""

    document_id: UUID
    title: str
    version: int
    score: float
    match_count: int
    snippets: list[SnippetResponse]


@dataclass
class SearchResponse:
    """One page of search hits."""

    hits: list[SearchHitResponse]
    total_count: int
    limit: int
    offset: int


@dataclass
class AiRedlineRequest:
    """An instruction for suggested redlines."""

    instruction: Annotated[str, Field(min_length=1, max_length=2000)]


@dataclass
class SuggestionResponse:
    """One suggestion pinned to the document version it was computed on."""

    suggestion_id: str
    start: int
    end: int
    original_text: str
    replacement: str
    rationale: str


@dataclass
class DroppedSuggestionResponse:
    """One suggestion that could not be pinned, and why."""

    suggestion_id: str
    text: str
    replacement: str
    rationale: str
    reason: DroppedSuggestionReason


@dataclass
class AiRedlineResponse:
    """Anchored and dropped suggestions for one document version."""

    document_id: UUID
    version: int
    suggestions: list[SuggestionResponse]
    dropped: list[DroppedSuggestionResponse]


@dataclass
class ErrorResponse:
    """The JSON body for every error."""

    error: str
    code: int
    error_type: ErrorType


def to_change(request: ChangeRequest, change_index: int) -> Change:
    """Map one request change onto an engine change."""
    target = request.target
    match target:
        case RangeTargetRequest(start=start, end=end):
            change_target = RangeTarget(start=start, end=end)
        case OccurrenceTargetRequest(text=text, occurrence=occurrence):
            change_target = OccurrenceTarget(text=text, occurrence=occurrence)
        case ContextTargetRequest(text=text, prefix=prefix, suffix=suffix):
            change_target = ContextTarget(text=text, prefix=prefix, suffix=suffix)
        case _:
            target_class = type(target).__name__
            logger.error(f"Unknown target class {target_class} for change {change_index}")
            raise InvalidTargetError(change_index, InvalidTargetReason.UNKNOWN_TARGET_TYPE)
    return Change(target=change_target, replacement=request.replacement)
