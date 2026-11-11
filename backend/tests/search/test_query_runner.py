from uuid import UUID

import pytest

from redline.search.errors import DocumentNotIndexedError
from redline.search.index import create_search_index, index_document
from redline.search.models import AllDocuments, SearchMatchMode, SelectedDocuments
from redline.search.query_parser import parse_query
from redline.search.query_runner import run_query

TITLE = "Notes"
VERSION = 1
FIRST_ID = UUID("00000000-0000-7000-8000-000000000041")
SECOND_ID = UUID("00000000-0000-7000-8000-000000000042")
THIRD_ID = UUID("00000000-0000-7000-8000-000000000040")
PAGE_LIMIT = 20
PAGE_OFFSET = 0


def test_document_missing_one_term_is_excluded() -> None:
    """A document that misses one term is not a hit."""
    index = create_search_index()
    index_document(index, FIRST_ID, TITLE, VERSION, "alpha only")
    index_document(index, SECOND_ID, TITLE, VERSION, "alpha beta")

    page = run_query(index, parse_query("alpha beta"), AllDocuments(), PAGE_LIMIT, PAGE_OFFSET)

    assert [hit.document_id for hit in page.hits] == [SECOND_ID]


def test_document_with_all_terms_is_included() -> None:
    """A document that contains every term is a hit."""
    index = create_search_index()
    index_document(index, FIRST_ID, TITLE, VERSION, "alpha beta")

    page = run_query(index, parse_query("alpha beta"), AllDocuments(), PAGE_LIMIT, PAGE_OFFSET)

    assert [hit.document_id for hit in page.hits] == [FIRST_ID]
    assert page.total_count == 1


def test_phrase_matches_consecutive_words() -> None:
    """A phrase matches words that sit next to each other."""
    index = create_search_index()
    index_document(index, FIRST_ID, TITLE, VERSION, "Please send written notice today.")

    page = run_query(
        index, parse_query('"written notice"'), AllDocuments(), PAGE_LIMIT, PAGE_OFFSET
    )

    assert [hit.document_id for hit in page.hits] == [FIRST_ID]


def test_phrase_does_not_match_across_paragraphs() -> None:
    """A phrase does not match words in different paragraphs."""
    index = create_search_index()
    index_document(index, FIRST_ID, TITLE, VERSION, "written\n\nnotice")

    page = run_query(
        index, parse_query('"written notice"'), AllDocuments(), PAGE_LIMIT, PAGE_OFFSET
    )

    assert page.hits == []
    assert page.total_count == 0


def test_phrase_words_apart_do_not_match() -> None:
    """A phrase does not match when another word sits between its words."""
    index = create_search_index()
    index_document(index, FIRST_ID, TITLE, VERSION, "written extra notice")

    page = run_query(
        index, parse_query('"written notice"'), AllDocuments(), PAGE_LIMIT, PAGE_OFFSET
    )

    assert page.hits == []


def test_selected_documents_limit_the_scope() -> None:
    """Selected documents exclude a match that was not selected."""
    index = create_search_index()
    index_document(index, FIRST_ID, TITLE, VERSION, "alpha beta")
    index_document(index, SECOND_ID, TITLE, VERSION, "alpha beta")

    page = run_query(
        index,
        parse_query("alpha"),
        SelectedDocuments(document_ids=[SECOND_ID]),
        PAGE_LIMIT,
        PAGE_OFFSET,
    )

    assert [hit.document_id for hit in page.hits] == [SECOND_ID]


def test_selected_unknown_document_raises_document_not_indexed_error() -> None:
    """A selected document that is not indexed raises DocumentNotIndexedError."""
    index = create_search_index()
    missing_id = UUID("00000000-0000-7000-8000-000000000099")

    with pytest.raises(DocumentNotIndexedError) as raised:
        run_query(
            index,
            parse_query("alpha"),
            SelectedDocuments(document_ids=[missing_id]),
            PAGE_LIMIT,
            PAGE_OFFSET,
        )

    assert raised.value.document_id == missing_id


def test_hits_are_ordered_by_score() -> None:
    """A higher score comes first, and equal scores are ordered by document id."""
    index = create_search_index()
    index_document(index, FIRST_ID, TITLE, VERSION, "alpha alpha beta beta")
    index_document(index, SECOND_ID, TITLE, VERSION, "alpha beta beta beta")

    page = run_query(index, parse_query("alpha"), AllDocuments(), PAGE_LIMIT, PAGE_OFFSET)

    assert [hit.document_id for hit in page.hits] == [FIRST_ID, SECOND_ID]
    assert page.hits[0].score > page.hits[1].score


def test_equal_scores_are_ordered_by_document_id() -> None:
    """Documents with the same score are ordered by document id."""
    index = create_search_index()
    index_document(index, FIRST_ID, TITLE, VERSION, "alpha beta")
    index_document(index, THIRD_ID, TITLE, VERSION, "alpha beta")

    page = run_query(index, parse_query("alpha"), AllDocuments(), PAGE_LIMIT, PAGE_OFFSET)

    assert [hit.document_id for hit in page.hits] == [THIRD_ID, FIRST_ID]


def test_paging_applies_limit_and_offset() -> None:
    """The page is sliced after the total is counted."""
    index = create_search_index()
    index_document(index, THIRD_ID, TITLE, VERSION, "alpha")
    index_document(index, FIRST_ID, TITLE, VERSION, "alpha alpha")
    index_document(index, SECOND_ID, TITLE, VERSION, "alpha alpha alpha")

    page = run_query(index, parse_query("alpha"), AllDocuments(), 1, 1)

    assert page.total_count == 3
    assert len(page.hits) == 1
    assert page.hits[0].document_id == FIRST_ID


def test_match_count_includes_terms_and_phrases() -> None:
    """The match count adds unquoted term counts and each phrase occurrence."""
    index = create_search_index()
    index_document(index, FIRST_ID, TITLE, VERSION, "alpha alpha beta beta")

    page = run_query(
        index, parse_query('alpha "beta beta"'), AllDocuments(), PAGE_LIMIT, PAGE_OFFSET
    )

    assert page.hits[0].match_count == 3


def test_snippets_are_the_first_matching_chunks_in_document_order() -> None:
    """Snippets are the first matching paragraphs, not a later one."""
    text = "nope.\n\nalpha one.\n\nskip.\n\nalpha two.\n\nalpha three.\n\nalpha four."
    index = create_search_index()
    index_document(index, FIRST_ID, TITLE, VERSION, text)

    page = run_query(index, parse_query("alpha"), AllDocuments(), PAGE_LIMIT, PAGE_OFFSET)

    snippets = page.hits[0].snippets
    assert len(snippets) == 3
    assert "one" in snippets[0].text
    assert "two" in snippets[1].text
    assert "three" in snippets[2].text
    assert "four" not in snippets[2].text


def test_prefix_term_matches_a_document_containing_any_expansion() -> None:
    """A prefix matches each document that contains any word starting that way."""
    index = create_search_index()
    index_document(index, FIRST_ID, TITLE, VERSION, "The party shall indemnify the company.")
    index_document(index, SECOND_ID, TITLE, VERSION, "The indemnity is mutual.")
    index_document(index, THIRD_ID, TITLE, VERSION, "No related wording here.")

    page = run_query(
        index,
        parse_query("indemn", SearchMatchMode.PREFIX),
        AllDocuments(),
        PAGE_LIMIT,
        PAGE_OFFSET,
    )

    assert {hit.document_id for hit in page.hits} == {FIRST_ID, SECOND_ID}


def test_prefix_term_with_no_expansions_matches_nothing() -> None:
    """A prefix that starts no indexed word matches nothing."""
    index = create_search_index()
    index_document(index, FIRST_ID, TITLE, VERSION, "alpha beta")

    page = run_query(
        index, parse_query("zzzz", SearchMatchMode.PREFIX), AllDocuments(), PAGE_LIMIT, PAGE_OFFSET
    )

    assert page.hits == []
    assert page.total_count == 0


def test_prefix_highlights_cover_every_expansion() -> None:
    """Highlights cover each word the prefix expanded to."""
    text = "The party shall indemnify the company, and the indemnity is mutual."
    index = create_search_index()
    index_document(index, FIRST_ID, TITLE, VERSION, text)

    page = run_query(
        index,
        parse_query("indemn", SearchMatchMode.PREFIX),
        AllDocuments(),
        PAGE_LIMIT,
        PAGE_OFFSET,
    )

    highlighted = {
        text[highlight.start : highlight.end] for highlight in page.hits[0].snippets[0].highlights
    }
    assert highlighted == {"indemnify", "indemnity"}


def test_exact_word_plus_prefix_term_both_must_match() -> None:
    """An earlier exact word and a prefix must both be present."""
    index = create_search_index()
    index_document(index, FIRST_ID, TITLE, VERSION, "Send written notice today.")
    index_document(index, SECOND_ID, TITLE, VERSION, "Send notice today.")
    index_document(index, THIRD_ID, TITLE, VERSION, "Send written mail today.")

    page = run_query(
        index,
        parse_query("written not", SearchMatchMode.PREFIX),
        AllDocuments(),
        PAGE_LIMIT,
        PAGE_OFFSET,
    )

    assert [hit.document_id for hit in page.hits] == [FIRST_ID]
