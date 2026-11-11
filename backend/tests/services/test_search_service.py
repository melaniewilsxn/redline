import logging
from datetime import UTC, datetime
from uuid import UUID

import pytest

from redline.editing.apply import apply_changes
from redline.editing.models import AppliedEdit, Change, RangeTarget
from redline.search.index import SearchIndex, index_document, update_indexed_document
from redline.search.models import AllDocuments, SearchMatchMode
from redline.services.search_service import SearchService
from redline.storage.models import StoredDocument

TITLE = "Notes"
VERSION = 1
NEXT_VERSION = 2
AUTHOR_TIME = datetime(2026, 1, 1, tzinfo=UTC)


def test_update_with_matching_base_version_uses_incremental_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A matching base version uses the incremental path, and search sees the new word."""
    service = SearchService()
    document = stored("Hello alpha")
    service.add_document(document)
    calls: list[str] = []

    def record_incremental(
        index: SearchIndex,
        document_id: UUID,
        version: int,
        text: str,
        applied_edits: list[AppliedEdit],
    ) -> None:
        """Record that the incremental path ran, then do the real update."""
        calls.append("incremental")
        update_indexed_document(index, document_id, version, text, applied_edits)

    monkeypatch.setattr(
        "redline.services.search_service.update_indexed_document", record_incremental
    )
    edited = apply_changes(
        document.text,
        [Change(target=RangeTarget(start=6, end=11), replacement="beta")],
    )
    updated = replace_text(document, edited.text, NEXT_VERSION)

    service.update_document(updated, edited.applied_edits, VERSION)
    page = service.search("beta", AllDocuments(), 10, 0, SearchMatchMode.EXACT)

    assert calls == ["incremental"]
    assert [hit.document_id for hit in page.hits] == [document.id]


def test_update_with_other_base_version_reindexes_document(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A base version that is not the indexed version reindexes the whole document."""
    service = SearchService()
    document = stored("Hello alpha")
    service.add_document(document)
    calls: list[str] = []

    def record_full(
        index: SearchIndex, document_id: UUID, title: str, version: int, text: str
    ) -> None:
        """Record that the full path ran, then index for real."""
        calls.append("full")
        index_document(index, document_id, title, version, text)

    monkeypatch.setattr("redline.services.search_service.index_document", record_full)
    updated = replace_text(document, "Hello beta", NEXT_VERSION)

    service.update_document(updated, [], VERSION + 5)
    page = service.search("beta", AllDocuments(), 10, 0, SearchMatchMode.EXACT)

    assert calls == ["full"]
    assert [hit.document_id for hit in page.hits] == [document.id]


def test_update_recovers_when_incremental_update_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """When the incremental update raises, the document is still searchable at its new text."""
    service = SearchService()
    document = stored("Hello alpha")
    service.add_document(document)

    def raise_incremental(
        index: SearchIndex,
        document_id: UUID,
        version: int,
        text: str,
        applied_edits: list[AppliedEdit],
    ) -> None:
        """Fail the incremental update."""
        raise RuntimeError("incremental failed")

    monkeypatch.setattr(
        "redline.services.search_service.update_indexed_document", raise_incremental
    )
    updated = replace_text(document, "Hello beta", NEXT_VERSION)

    service.update_document(updated, [], VERSION)
    page = service.search("beta", AllDocuments(), 10, 0, SearchMatchMode.EXACT)

    assert [hit.document_id for hit in page.hits] == [document.id]


def test_update_logs_and_continues_when_full_reindex_also_fails(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """When both update paths fail, the error is logged and no exception escapes."""
    service = SearchService()
    document = stored("Hello alpha")
    service.add_document(document)

    def raise_failure(*args: object) -> None:
        """Fail either index update."""
        raise RuntimeError("index failed")

    monkeypatch.setattr("redline.services.search_service.update_indexed_document", raise_failure)
    monkeypatch.setattr("redline.services.search_service.index_document", raise_failure)
    updated = replace_text(document, "Hello beta", NEXT_VERSION)

    with caplog.at_level(logging.ERROR):
        service.update_document(updated, [], VERSION)

    assert any(record.levelno >= logging.ERROR for record in caplog.records)


def test_add_document_failure_does_not_raise(monkeypatch: pytest.MonkeyPatch) -> None:
    """A failed index of a new document does not raise."""
    service = SearchService()

    def raise_failure(*args: object) -> None:
        """Fail the index."""
        raise RuntimeError("index failed")

    monkeypatch.setattr("redline.services.search_service.index_document", raise_failure)

    service.add_document(stored("Hello alpha"))
    page = service.search("alpha", AllDocuments(), 10, 0, SearchMatchMode.EXACT)

    assert page.hits == []


def test_stale_indexed_version_is_refreshed_before_choosing_spans() -> None:
    """A newer document version is indexed before its spans are chosen."""
    service = SearchService()
    document = stored("Hello alpha")
    service.add_document(document)
    updated = replace_text(document, "Hello indemnity beta", NEXT_VERSION)

    spans = service.find_relevant_spans(updated, "indemnity", 3)

    assert service.index.documents[document.id].version == NEXT_VERSION
    assert service.index.documents[document.id].text == updated.text
    assert "indemnity" in updated.text[spans[0].start : spans[0].end]


def test_document_missing_from_index_is_indexed_before_choosing_spans() -> None:
    """A document that was never indexed is indexed before its spans are chosen."""
    service = SearchService()
    document = stored("Hello indemnity")

    spans = service.find_relevant_spans(document, "indemnity", 3)

    assert service.index.documents[document.id].version == VERSION
    assert service.index.documents[document.id].text == document.text
    assert spans


def test_current_indexed_version_is_kept(monkeypatch: pytest.MonkeyPatch) -> None:
    """A document already indexed at this version is not indexed again."""
    service = SearchService()
    document = stored("Hello indemnity")
    service.add_document(document)
    calls: list[str] = []

    def record_index(*args: object) -> None:
        """Record an index call."""
        calls.append("indexed")

    monkeypatch.setattr("redline.services.search_service.index_document", record_index)

    spans = service.find_relevant_spans(document, "indemnity", 3)

    assert calls == []
    assert spans


def stored(text: str) -> StoredDocument:
    """Build one stored document."""
    return StoredDocument(
        id=UUID("00000000-0000-7000-8000-000000000050"),
        title=TITLE,
        version=VERSION,
        text=text,
        created_at=AUTHOR_TIME,
        updated_at=AUTHOR_TIME,
    )


def replace_text(document: StoredDocument, text: str, version: int) -> StoredDocument:
    """Return the same document with different text and version."""
    return StoredDocument(
        id=document.id,
        title=document.title,
        version=version,
        text=text,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )
