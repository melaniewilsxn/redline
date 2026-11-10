from uuid import UUID

import pytest
from psycopg import Connection

from redline.editing.errors import TargetNotFoundError
from redline.editing.models import Change, OccurrenceTarget, RangeTarget
from redline.services.document_service import (
    APPLIED_CHANGES_SUMMARY,
    CREATED_DOCUMENT_SUMMARY,
    FIRST_VERSION,
    apply_document_changes,
    create_document,
)
from redline.services.errors import StaleVersionError
from redline.storage.document_repository import (
    advance_document_version,
    get_current_version,
    get_document,
    get_document_version,
    insert_document_version,
)
from redline.storage.errors import DocumentVersionNotFoundError
from redline.storage.models import StoredDocument


def test_create_document_stores_version_one(connection: Connection) -> None:
    """Creating a document stores version 1 with the author and summary."""
    document = create_document(connection, "Notes", "Hello", "Ada")

    stored = get_document_version(connection, document.id, FIRST_VERSION)

    assert document.version == FIRST_VERSION
    assert document.text == "Hello"
    assert stored.author == "Ada"
    assert stored.summary == CREATED_DOCUMENT_SUMMARY


def test_apply_changes_creates_next_version_with_author_and_summary(connection: Connection) -> None:
    """A successful batch writes the next version, the author, and the summary."""
    document = create_document(connection, "Notes", "Hello", "Ada")
    changes = [Change(target=RangeTarget(start=0, end=1), replacement="J")]

    applied = apply_document_changes(connection, document.id, document.version, changes, "Grace")

    stored = get_document_version(connection, document.id, document.version + 1)
    assert applied.document.text == "Jello"
    assert applied.document.version == document.version + 1
    assert applied.applied_edits[0].span.start == 0
    assert stored.author == "Grace"
    assert stored.summary == APPLIED_CHANGES_SUMMARY.format(change_count=1)


def test_apply_changes_with_stale_expected_version_raises_stale_version_error(
    connection: Connection,
) -> None:
    """A write for a version that is already old does not create another version."""
    document = create_document(connection, "Notes", "Hello", "Ada")
    changes = [Change(target=RangeTarget(start=0, end=1), replacement="J")]

    with pytest.raises(StaleVersionError) as raised:
        apply_document_changes(connection, document.id, document.version + 1, changes, "Grace")

    assert raised.value.expected_version == document.version + 1
    assert raised.value.current_version == document.version
    with pytest.raises(DocumentVersionNotFoundError):
        get_document_version(connection, document.id, document.version + 1)


def test_lost_race_raises_stale_version_error_and_saves_nothing(
    connection: Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The compare-and-swap rejects a write that lost between the read and the update."""
    saved = create_document(connection, "Notes", "Hello", "Ada")
    advance_document_version(connection, saved.id, saved.version)
    insert_document_version(connection, saved.id, saved.version + 1, "Hello", "Bea", "Other writer")

    def return_saved_document(connection: Connection, document_id: UUID) -> StoredDocument:
        """Return the snapshot taken before the other writer."""
        return saved

    monkeypatch.setattr("redline.services.document_service.get_document", return_saved_document)
    changes = [Change(target=RangeTarget(start=0, end=1), replacement="J")]

    with pytest.raises(StaleVersionError) as raised:
        apply_document_changes(connection, saved.id, saved.version, changes, "Grace")

    assert raised.value.expected_version == saved.version
    assert raised.value.current_version == saved.version + 1
    assert get_current_version(connection, saved.id) == saved.version + 1
    with pytest.raises(DocumentVersionNotFoundError):
        get_document_version(connection, saved.id, saved.version + 2)


def test_engine_error_leaves_document_unchanged(connection: Connection) -> None:
    """A target the engine cannot resolve does not write a new version."""
    document = create_document(connection, "Notes", "Hello", "Ada")
    changes = [Change(target=OccurrenceTarget(text="missing", occurrence=1), replacement="x")]

    with pytest.raises(TargetNotFoundError):
        apply_document_changes(connection, document.id, document.version, changes, "Grace")

    assert get_document(connection, document.id).version == FIRST_VERSION
    with pytest.raises(DocumentVersionNotFoundError):
        get_document_version(connection, document.id, FIRST_VERSION + 1)
