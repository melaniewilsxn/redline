from uuid import UUID

from redline.editing.apply import apply_changes
from redline.editing.models import Change, RangeTarget
from redline.search.chunker import split_into_chunks
from redline.search.index import (
    SearchIndex,
    create_search_index,
    index_document,
    update_indexed_document,
)

DOCUMENT_ID = UUID("00000000-0000-7000-8000-000000000010")
OTHER_DOCUMENT_ID = UUID("00000000-0000-7000-8000-000000000011")
TITLE = "Notes"
CURRENT_VERSION = 1
NEXT_VERSION = 2


def test_index_document_records_term_documents() -> None:
    """Indexing a document records which terms it contains, and how often."""
    index = create_search_index()

    index_document(index, DOCUMENT_ID, TITLE, CURRENT_VERSION, "Alpha beta. Alpha.")

    document = index.documents[DOCUMENT_ID]
    assert index.term_documents["alpha"] == {DOCUMENT_ID}
    assert index.term_documents["beta"] == {DOCUMENT_ID}
    assert document.term_counts["alpha"] == 2
    assert document.term_counts["beta"] == 1


def test_index_document_twice_replaces_earlier_entry() -> None:
    """Indexing the same document again drops terms the new text does not contain."""
    index = create_search_index()
    index_document(index, OTHER_DOCUMENT_ID, "Other", CURRENT_VERSION, "Alpha stays.")
    index_document(index, DOCUMENT_ID, TITLE, CURRENT_VERSION, "Alpha beta.")

    index_document(index, DOCUMENT_ID, TITLE, NEXT_VERSION, "Beta only.")

    assert index.documents[DOCUMENT_ID].text == "Beta only."
    assert index.documents[DOCUMENT_ID].version == NEXT_VERSION
    assert "alpha" not in index.documents[DOCUMENT_ID].term_counts
    assert index.term_documents["alpha"] == {OTHER_DOCUMENT_ID}
    assert index.term_documents["beta"] == {DOCUMENT_ID}


def test_chunk_occurrences_use_chunk_relative_spans() -> None:
    """A token's span is relative to its chunk, and its position counts from zero."""
    text = "Alpha.\n\nBeta."
    index = create_search_index()

    index_document(index, DOCUMENT_ID, TITLE, CURRENT_VERSION, text)

    chunk = index.documents[DOCUMENT_ID].chunks[1]
    occurrence = chunk.term_occurrences["beta"][0]
    assert occurrence.position == 0
    assert occurrence.span.start == 0
    absolute_start = chunk.start + occurrence.span.start
    absolute_end = chunk.start + occurrence.span.end
    assert text[absolute_start:absolute_end] == "Beta"


def test_incremental_update_matches_full_reindex_for_edit_inside_paragraph() -> None:
    """An edit inside a paragraph matches indexing the new text from scratch."""
    text = "Alpha word stays here.\n\nBeta word stays here."
    start = text.index("word")
    changes = [Change(target=RangeTarget(start=start, end=start + len("word")), replacement="term")]

    assert_incremental_matches_full(text, changes)


def test_incremental_update_matches_full_reindex_for_edit_removing_paragraph_break() -> None:
    """Deleting the blank line merges the paragraphs the same way a full index would."""
    text = "Alpha.\n\nBeta."
    start = text.index("\n\n")
    changes = [Change(target=RangeTarget(start=start, end=start + 2), replacement="")]

    assert_incremental_matches_full(text, changes)


def test_incremental_update_matches_full_reindex_for_edit_adding_paragraph_break() -> None:
    """Inserting a blank line splits a paragraph the same way a full index would."""
    text = "Alpha word and Beta word."
    start = text.index(" and ")
    changes = [Change(target=RangeTarget(start=start, end=start), replacement="\n\n")]

    assert_incremental_matches_full(text, changes)


def test_incremental_update_matches_full_reindex_for_insert_at_chunk_boundary() -> None:
    """An insert on the boundary between two chunks is counted once."""
    text = "Alpha paragraph stays.\n\nBeta paragraph stays."
    boundary = split_into_chunks(text, 0)[0].end
    changes = [Change(target=RangeTarget(start=boundary, end=boundary), replacement="X")]

    assert_incremental_matches_full(text, changes)


def test_incremental_update_matches_full_reindex_for_insert_at_document_start() -> None:
    """An insert at the start of the document is counted once."""
    text = "Alpha paragraph stays.\n\nBeta paragraph stays."
    changes = [Change(target=RangeTarget(start=0, end=0), replacement="X")]

    assert_incremental_matches_full(text, changes)


def test_incremental_update_matches_full_reindex_for_insert_at_document_end() -> None:
    """An insert at the end of the document is counted once."""
    text = "Alpha paragraph stays.\n\nBeta paragraph stays."
    changes = [Change(target=RangeTarget(start=len(text), end=len(text)), replacement="END")]

    assert_incremental_matches_full(text, changes)


def test_incremental_update_matches_full_reindex_for_inserts_on_both_edges_of_one_chunk() -> None:
    """Inserts on both edges of one chunk are each counted once."""
    text = "Alpha paragraph stays."
    changes = [
        Change(target=RangeTarget(start=0, end=0), replacement="START"),
        Change(target=RangeTarget(start=len(text), end=len(text)), replacement="END"),
    ]

    assert_incremental_matches_full(text, changes)


def test_incremental_update_matches_full_reindex_for_edits_in_separate_paragraphs() -> None:
    """Edits in paragraphs that do not share a neighbor stay in separate runs."""
    parts = [
        "One alpha stays.",
        "Two beta stays.",
        "Three gamma stays.",
        "Four delta stays.",
        "Five epsilon stays.",
    ]
    text = "\n\n".join(parts)
    alpha = text.index("alpha")
    epsilon = text.index("epsilon")
    changes = [
        Change(target=RangeTarget(start=alpha, end=alpha + len("alpha")), replacement="ALP"),
        Change(target=RangeTarget(start=epsilon, end=epsilon + len("epsilon")), replacement="EPS"),
    ]

    assert_incremental_matches_full(text, changes)


def test_incremental_update_matches_full_reindex_for_insert_into_empty_document() -> None:
    """An insert into an empty document matches indexing the new text."""
    changes = [Change(target=RangeTarget(start=0, end=0), replacement="Hello")]

    assert_incremental_matches_full("", changes)


def test_term_removed_by_edit_leaves_term_documents() -> None:
    """A term an edit removes is dropped from the term map."""
    text = "alpha beta"
    changes = [Change(target=RangeTarget(start=0, end=len("alpha")), replacement="other")]

    index = assert_incremental_matches_full(text, changes)

    assert "alpha" not in index.term_documents


def test_term_added_by_edit_joins_term_documents() -> None:
    """A term an edit adds is recorded in the term map."""
    text = "alpha beta"
    changes = [Change(target=RangeTarget(start=len(text), end=len(text)), replacement=" gamma")]

    index = assert_incremental_matches_full(text, changes)

    assert index.term_documents["gamma"] == {DOCUMENT_ID}


def assert_incremental_matches_full(text: str, changes: list[Change]) -> SearchIndex:
    """Apply changes incrementally and check the index against a full re-index."""
    edited = apply_changes(text, changes)
    incremental = create_search_index()
    index_document(incremental, DOCUMENT_ID, TITLE, CURRENT_VERSION, text)
    update_indexed_document(
        incremental, DOCUMENT_ID, NEXT_VERSION, edited.text, edited.applied_edits
    )
    fresh = create_search_index()
    index_document(fresh, DOCUMENT_ID, TITLE, NEXT_VERSION, edited.text)
    assert_same_index(incremental, fresh)
    return incremental


def assert_same_index(left: SearchIndex, right: SearchIndex) -> None:
    """The two indexes hold the same document and the same term map."""
    left_document = left.documents[DOCUMENT_ID]
    right_document = right.documents[DOCUMENT_ID]
    assert left_document.version == right_document.version
    assert left_document.text == right_document.text
    assert left_document.token_count == right_document.token_count
    assert left_document.term_counts == right_document.term_counts
    assert len(left_document.chunks) == len(right_document.chunks)
    for left_chunk, right_chunk in zip(left_document.chunks, right_document.chunks, strict=True):
        assert left_chunk.start == right_chunk.start
        assert left_chunk.length == right_chunk.length
        assert left_chunk.token_count == right_chunk.token_count
        assert left_chunk.term_occurrences == right_chunk.term_occurrences
    assert left.term_documents == right.term_documents
