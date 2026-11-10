from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class StoredDocument:
    """A document and the text of its current version."""

    id: UUID
    title: str
    version: int
    text: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class DocumentSummary:
    """A document without its text, for a list."""

    id: UUID
    title: str
    version: int
    character_count: int
    updated_at: datetime


@dataclass(frozen=True)
class DocumentPage:
    """One page of document summaries and the total number of documents."""

    documents: list[DocumentSummary]
    total_count: int


@dataclass(frozen=True)
class DocumentVersion:
    """The full text of one saved version."""

    document_id: UUID
    version: int
    text: str
    author: str
    summary: str
    created_at: datetime


@dataclass(frozen=True)
class VersionSummary:
    """One saved version without its text."""

    version: int
    author: str
    summary: str
    character_count: int
    created_at: datetime
