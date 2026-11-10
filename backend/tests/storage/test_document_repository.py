import uuid

import psycopg
import pytest
from psycopg import Connection

from redline.storage.document_repository import (
    INITIAL_DOCUMENT_VERSION,
    advance_document_version,
    get_current_version,
    get_document,
    get_document_version,
    insert_document,
    insert_document_version,
    list_document_versions,
    list_documents,
)
from redline.storage.errors import DocumentNotFoundError, DocumentVersionNotFoundError


def test_inserted_document_reads_back_with_its_first_version(connection: Connection) -> None:
    """A document and its first version come back with the text that was stored."""
    document_id = uuid.uuid7()
    insert_document(connection, document_id, "Notes")
    insert_document_version(
        connection, document_id, INITIAL_DOCUMENT_VERSION, "Hello", "Ada", "Created"
    )

    document = get_document(connection, document_id)

    assert document.id == document_id
    assert document.title == "Notes"
    assert document.version == INITIAL_DOCUMENT_VERSION
    assert document.text == "Hello"


def test_get_missing_document_raises_document_not_found_error(connection: Connection) -> None:
    """Reading an unknown id raises DocumentNotFoundError."""
    document_id = uuid.uuid7()

    with pytest.raises(DocumentNotFoundError) as raised:
        get_document(connection, document_id)

    assert raised.value.document_id == document_id


def test_advance_document_version_succeeds_with_current_version(connection: Connection) -> None:
    """Advancing from the current version claims the next one."""
    document_id = uuid.uuid7()
    insert_document(connection, document_id, "Notes")

    claimed = advance_document_version(connection, document_id, INITIAL_DOCUMENT_VERSION)

    assert claimed is True
    assert get_current_version(connection, document_id) == INITIAL_DOCUMENT_VERSION + 1


def test_advance_document_version_fails_with_stale_version(connection: Connection) -> None:
    """A second advance with the same expected version does not claim the row."""
    document_id = uuid.uuid7()
    insert_document(connection, document_id, "Notes")
    advance_document_version(connection, document_id, INITIAL_DOCUMENT_VERSION)

    claimed = advance_document_version(connection, document_id, INITIAL_DOCUMENT_VERSION)

    assert claimed is False
    assert get_current_version(connection, document_id) == INITIAL_DOCUMENT_VERSION + 1


def test_duplicate_version_insert_is_rejected(connection: Connection) -> None:
    """Two rows cannot share a document id and version."""
    document_id = uuid.uuid7()
    insert_document(connection, document_id, "Notes")
    insert_document_version(
        connection, document_id, INITIAL_DOCUMENT_VERSION, "Hello", "Ada", "Created"
    )

    with pytest.raises(psycopg.errors.UniqueViolation), connection.transaction():
        insert_document_version(
            connection, document_id, INITIAL_DOCUMENT_VERSION, "Again", "Ada", "Created"
        )


def test_list_document_versions_returns_newest_first(connection: Connection) -> None:
    """Versions come back with the highest number first."""
    document_id = uuid.uuid7()
    insert_document(connection, document_id, "Notes")
    insert_document_version(connection, document_id, 1, "First", "Ada", "Created")
    insert_document_version(connection, document_id, 2, "Second", "Ada", "Edited")

    versions = list_document_versions(connection, document_id)

    assert [version.version for version in versions] == [2, 1]
    assert versions[1].character_count == len("First")


def test_list_versions_of_missing_document_raises_document_not_found_error(
    connection: Connection,
) -> None:
    """An unknown document has no version list."""
    document_id = uuid.uuid7()

    with pytest.raises(DocumentNotFoundError) as raised:
        list_document_versions(connection, document_id)

    assert raised.value.document_id == document_id


def test_get_missing_document_version_raises_document_version_not_found_error(
    connection: Connection,
) -> None:
    """A missing version number raises DocumentVersionNotFoundError."""
    document_id = uuid.uuid7()
    insert_document(connection, document_id, "Notes")
    insert_document_version(connection, document_id, 1, "Hello", "Ada", "Created")

    with pytest.raises(DocumentVersionNotFoundError) as raised:
        get_document_version(connection, document_id, 2)

    assert raised.value.document_id == document_id
    assert raised.value.version == 2


def test_list_documents_pages_with_limit_and_offset(connection: Connection) -> None:
    """Limit and offset walk the same order the full list uses."""
    before = list_documents(connection, limit=1, offset=0)
    document_ids = [uuid.uuid7() for _number in range(3)]
    for document_id in document_ids:
        insert_document(connection, document_id, "Notes")
        insert_document_version(connection, document_id, 1, "Hello", "Ada", "Created")
    full_page = list_documents(connection, limit=before.total_count + 3, offset=0)

    first_page = list_documents(connection, limit=1, offset=0)
    second_page = list_documents(connection, limit=1, offset=1)

    assert full_page.total_count == before.total_count + 3
    assert [document.id for document in first_page.documents] == [full_page.documents[0].id]
    assert [document.id for document in second_page.documents] == [full_page.documents[1].id]
    assert first_page.total_count == full_page.total_count
    stored = next(document for document in full_page.documents if document.id == document_ids[0])
    assert stored.character_count == len("Hello")


def test_list_documents_page_past_end_keeps_total_count(connection: Connection) -> None:
    """A page past the end is empty and still reports how many documents exist."""
    document_id = uuid.uuid7()
    insert_document(connection, document_id, "Notes")
    insert_document_version(connection, document_id, 1, "Hello", "Ada", "Created")
    existing = list_documents(connection, limit=1, offset=0)

    past_end = list_documents(connection, limit=1, offset=existing.total_count + 5)

    assert past_end.documents == []
    assert past_end.total_count == existing.total_count


def test_get_current_version_of_missing_document_raises_document_not_found_error(
    connection: Connection,
) -> None:
    """The current version of an unknown document raises DocumentNotFoundError."""
    document_id = uuid.uuid7()

    with pytest.raises(DocumentNotFoundError) as raised:
        get_current_version(connection, document_id)

    assert raised.value.document_id == document_id
