import logging
from datetime import datetime
from uuid import UUID

from psycopg import Connection
from psycopg.rows import class_row

from redline.storage.errors import DocumentNotFoundError, DocumentVersionNotFoundError, StorageError
from redline.storage.models import (
    DocumentPage,
    DocumentSummary,
    DocumentVersion,
    StoredDocument,
    VersionSummary,
)

logger = logging.getLogger(__name__)

INITIAL_DOCUMENT_VERSION = 1

INSERT_DOCUMENT = """
INSERT INTO documents (id, title, current_version)
VALUES (%s, %s, %s)
"""

INSERT_DOCUMENT_VERSION = """
INSERT INTO document_versions (document_id, version, text, author, summary)
VALUES (%s, %s, %s, %s, %s)
"""

ADVANCE_DOCUMENT_VERSION = """
UPDATE documents
SET current_version = current_version + 1, updated_at = now()
WHERE id = %s AND current_version = %s
"""

LIST_CURRENT_DOCUMENTS = """
SELECT
    documents.id,
    documents.title,
    documents.current_version AS version,
    document_versions.text,
    documents.created_at,
    documents.updated_at
FROM documents
JOIN document_versions
    ON document_versions.document_id = documents.id
    AND document_versions.version = documents.current_version
"""

GET_DOCUMENT = """
SELECT
    documents.id,
    documents.title,
    documents.current_version AS version,
    document_versions.text,
    documents.created_at,
    documents.updated_at
FROM documents
JOIN document_versions
    ON document_versions.document_id = documents.id
    AND document_versions.version = documents.current_version
WHERE documents.id = %s
"""

LIST_DOCUMENT_SUMMARIES = """
SELECT
    documents.id,
    documents.title,
    documents.current_version AS version,
    char_length(document_versions.text) AS character_count,
    documents.updated_at
FROM documents
JOIN document_versions
    ON document_versions.document_id = documents.id
    AND document_versions.version = documents.current_version
ORDER BY documents.updated_at DESC, documents.id
LIMIT %s OFFSET %s
"""

COUNT_DOCUMENTS = "SELECT count(*) FROM documents"

LIST_DOCUMENT_VERSIONS = """
SELECT
    version,
    author,
    summary,
    char_length(text) AS character_count,
    created_at
FROM document_versions
WHERE document_id = %s
ORDER BY version DESC
"""

GET_DOCUMENT_VERSION = """
SELECT document_id, version, text, author, summary, created_at
FROM document_versions
WHERE document_id = %s AND version = %s
"""

GET_DOCUMENT_UPDATED_AT = "SELECT updated_at FROM documents WHERE id = %s"

GET_CURRENT_VERSION = "SELECT current_version FROM documents WHERE id = %s"


def insert_document(connection: Connection, document_id: UUID, title: str) -> None:
    """Insert a document row at version 1."""
    connection.execute(INSERT_DOCUMENT, (document_id, title, INITIAL_DOCUMENT_VERSION))


def insert_document_version(
    connection: Connection,
    document_id: UUID,
    version: int,
    text: str,
    author: str,
    summary: str,
) -> None:
    """Insert one saved version of a document."""
    connection.execute(
        INSERT_DOCUMENT_VERSION,
        (document_id, version, text, author, summary),
    )


def advance_document_version(
    connection: Connection, document_id: UUID, expected_version: int
) -> bool:
    """Claim the next version when the row is still at expected_version."""
    cursor = connection.execute(ADVANCE_DOCUMENT_VERSION, (document_id, expected_version))
    return cursor.rowcount == 1


def list_current_documents(connection: Connection) -> list[StoredDocument]:
    """Return every document with its current text."""
    with connection.cursor(row_factory=class_row(StoredDocument)) as cursor:
        cursor.execute(LIST_CURRENT_DOCUMENTS)
        return list(cursor.fetchall())


def get_document(connection: Connection, document_id: UUID) -> StoredDocument:
    """Return a document joined to its current version."""
    with connection.cursor(row_factory=class_row(StoredDocument)) as cursor:
        cursor.execute(GET_DOCUMENT, (document_id,))
        document = cursor.fetchone()
    if document is None:
        logger.warning(f"Document {document_id} was not found")
        raise DocumentNotFoundError(document_id)
    return document


def list_documents(connection: Connection, limit: int, offset: int) -> DocumentPage:
    """Return one page of summaries and the total number of documents."""
    with connection.cursor(row_factory=class_row(DocumentSummary)) as cursor:
        cursor.execute(LIST_DOCUMENT_SUMMARIES, (limit, offset))
        documents = list(cursor.fetchall())
    count_row = connection.execute(COUNT_DOCUMENTS).fetchone()
    if count_row is None:
        logger.error("Document count returned no row")
        raise StorageError("Document count returned no row")
    return DocumentPage(documents=documents, total_count=int(count_row[0]))


def list_document_versions(connection: Connection, document_id: UUID) -> list[VersionSummary]:
    """Return every version of a document, newest first."""
    with connection.cursor(row_factory=class_row(VersionSummary)) as cursor:
        cursor.execute(LIST_DOCUMENT_VERSIONS, (document_id,))
        versions = list(cursor.fetchall())
    if not versions:
        logger.warning(f"Document {document_id} was not found")
        raise DocumentNotFoundError(document_id)
    return versions


def get_document_version(
    connection: Connection, document_id: UUID, version: int
) -> DocumentVersion:
    """Return one saved version, including its text."""
    with connection.cursor(row_factory=class_row(DocumentVersion)) as cursor:
        cursor.execute(GET_DOCUMENT_VERSION, (document_id, version))
        document_version = cursor.fetchone()
    if document_version is None:
        logger.warning(f"Document {document_id} has no version {version}")
        raise DocumentVersionNotFoundError(document_id, version)
    return document_version


def get_document_updated_at(connection: Connection, document_id: UUID) -> datetime:
    """Return when the document row was last updated."""
    row = connection.execute(GET_DOCUMENT_UPDATED_AT, (document_id,)).fetchone()
    if row is None:
        logger.warning(f"Document {document_id} was not found")
        raise DocumentNotFoundError(document_id)
    updated_at: datetime = row[0]
    return updated_at


def get_current_version(connection: Connection, document_id: UUID) -> int:
    """Return the current version number of a document."""
    row = connection.execute(GET_CURRENT_VERSION, (document_id,)).fetchone()
    if row is None:
        logger.warning(f"Document {document_id} was not found")
        raise DocumentNotFoundError(document_id)
    return int(row[0])
