import logging
import uuid
from dataclasses import dataclass
from typing import NoReturn
from uuid import UUID

from psycopg import Connection

from redline.editing.apply import apply_changes
from redline.editing.models import AppliedEdit, Change
from redline.services.errors import StaleVersionError
from redline.services.search_service import SearchService
from redline.storage.document_repository import (
    INITIAL_DOCUMENT_VERSION,
    advance_document_version,
    get_current_version,
    get_document,
    get_document_updated_at,
    insert_document,
    insert_document_version,
)
from redline.storage.models import StoredDocument

logger = logging.getLogger(__name__)

CREATED_DOCUMENT_SUMMARY = "Created document"
APPLIED_CHANGES_SUMMARY = "Applied {change_count} changes"


@dataclass(frozen=True)
class AppliedDocumentChanges:
    """A document after a batch of changes, and where each edit landed."""

    document: StoredDocument
    applied_edits: list[AppliedEdit]


def create_document(
    connection: Connection,
    title: str,
    text: str,
    author: str,
    search_service: SearchService,
) -> StoredDocument:
    """Store a new document and its first version, then add it to the index."""
    logger.info(f"Started creating a document of {len(text)} characters")
    document_id = uuid.uuid7()
    with connection.transaction():
        insert_document(connection, document_id, title)
        insert_document_version(
            connection,
            document_id,
            INITIAL_DOCUMENT_VERSION,
            text,
            author,
            CREATED_DOCUMENT_SUMMARY,
        )
    document = get_document(connection, document_id)
    search_service.add_document(document)
    logger.info(f"Finished creating document {document.id} at version {document.version}")
    return document


def apply_document_changes(
    connection: Connection,
    document_id: UUID,
    expected_version: int,
    changes: list[Change],
    author: str,
    search_service: SearchService,
) -> AppliedDocumentChanges:
    """Apply a batch of changes when the document is still at the expected version."""
    logger.info(
        f"Started applying {len(changes)} changes to document {document_id} "
        f"at version {expected_version}"
    )
    document = get_document(connection, document_id)
    if document.version != expected_version:
        raise_stale_version(document_id, expected_version, document.version)
    edited = apply_changes(document.text, changes)
    next_version = expected_version + 1
    with connection.transaction():
        claimed = advance_document_version(connection, document_id, expected_version)
        if not claimed:
            current_version = get_current_version(connection, document_id)
            raise_stale_version(document_id, expected_version, current_version)
        insert_document_version(
            connection,
            document_id,
            next_version,
            edited.text,
            author,
            APPLIED_CHANGES_SUMMARY.format(change_count=len(changes)),
        )
    updated_at = get_document_updated_at(connection, document_id)
    stored = StoredDocument(
        id=document.id,
        title=document.title,
        version=next_version,
        text=edited.text,
        created_at=document.created_at,
        updated_at=updated_at,
    )
    search_service.update_document(stored, edited.applied_edits, expected_version)
    logger.info(
        f"Finished applying changes to document {document_id} "
        f"at version {stored.version}, length {len(stored.text)}"
    )
    return AppliedDocumentChanges(document=stored, applied_edits=edited.applied_edits)


def raise_stale_version(document_id: UUID, expected_version: int, current_version: int) -> NoReturn:
    """Log a stale write and raise."""
    logger.warning(
        f"Rejected stale write to document {document_id}: "
        f"expected version {expected_version}, current version {current_version}"
    )
    raise StaleVersionError(document_id, expected_version, current_version)
