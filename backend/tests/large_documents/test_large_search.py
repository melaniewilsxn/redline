from uuid import UUID

from redline.editing.apply import apply_changes
from redline.search.index import (
    SearchIndex,
    create_search_index,
    index_document,
    update_indexed_document,
)
from redline.search.models import AllDocuments
from redline.search.query_parser import parse_query
from redline.search.query_runner import run_query
from tests.fixtures.large_contract import (
    LARGE_DOCUMENT_CHARACTER_COUNT,
    build_large_contract,
    build_spread_changes,
    section_number_at,
)

DOCUMENT_ID = UUID("00000000-0000-7000-8000-000000000060")
TITLE = "Large contract"
CURRENT_VERSION = 1
NEXT_VERSION = 2
LATE_SECTION_FRACTION = 0.9
PAGE_LIMIT = 5
PAGE_OFFSET = 0


def test_incremental_update_matches_full_reindex_on_large_document() -> None:
    """A thousand spread edits, applied incrementally, match indexing the result from scratch."""
    text = build_large_contract(LARGE_DOCUMENT_CHARACTER_COUNT)
    edited = apply_changes(text, build_spread_changes(len(text)))
    incremental = create_search_index()
    index_document(incremental, DOCUMENT_ID, TITLE, CURRENT_VERSION, text)

    update_indexed_document(
        incremental, DOCUMENT_ID, NEXT_VERSION, edited.text, edited.applied_edits
    )
    fresh = create_search_index()
    index_document(fresh, DOCUMENT_ID, TITLE, NEXT_VERSION, edited.text)

    assert_same_index(incremental, fresh)


def test_phrase_near_end_of_large_document_is_found() -> None:
    """A phrase near the end of a 10MB contract is found, and the highlight covers it."""
    text = build_large_contract(LARGE_DOCUMENT_CHARACTER_COUNT)
    section_number = section_number_at(text, LATE_SECTION_FRACTION)
    phrase = f"Schedule {section_number} to the Customer"
    index = create_search_index()
    index_document(index, DOCUMENT_ID, TITLE, CURRENT_VERSION, text)

    page = run_query(index, parse_query(f'"{phrase}"'), AllDocuments(), PAGE_LIMIT, PAGE_OFFSET)

    assert page.total_count == 1
    highlights = [
        highlight for snippet in page.hits[0].snippets for highlight in snippet.highlights
    ]
    assert any(text[highlight.start : highlight.end] == phrase for highlight in highlights)


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
