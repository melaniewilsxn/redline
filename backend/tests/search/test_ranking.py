from uuid import UUID

from redline.search.index import create_search_index, index_document
from redline.search.ranking import score_bm25

RARE_DOCUMENT_ID = UUID("00000000-0000-7000-8000-000000000021")
COMMON_DOCUMENT_ID = UUID("00000000-0000-7000-8000-000000000022")
SHORT_DOCUMENT_ID = UUID("00000000-0000-7000-8000-000000000023")
LONG_DOCUMENT_ID = UUID("00000000-0000-7000-8000-000000000024")
TITLE = "Notes"
VERSION = 1
PADDING = " gamma" * 5


def test_rarer_term_scores_higher() -> None:
    """With equal counts, the document holding the rarer term scores higher."""
    index = create_search_index()
    index_document(index, RARE_DOCUMENT_ID, TITLE, VERSION, "quartz" + PADDING)
    index_document(index, COMMON_DOCUMENT_ID, TITLE, VERSION, "apple" + PADDING)
    for number in range(5):
        index_document(
            index,
            UUID(f"00000000-0000-7000-8000-00000000003{number}"),
            TITLE,
            VERSION,
            "apple" + PADDING,
        )

    rare_score = score_bm25(index, index.documents[RARE_DOCUMENT_ID], ["quartz"])
    common_score = score_bm25(index, index.documents[COMMON_DOCUMENT_ID], ["apple"])
    ranked = sorted(
        [(rare_score, RARE_DOCUMENT_ID), (common_score, COMMON_DOCUMENT_ID)],
        key=lambda scored: (-scored[0], scored[1]),
    )

    assert ranked[0][1] == RARE_DOCUMENT_ID


def test_more_occurrences_score_higher() -> None:
    """The same term scores higher in the document that contains it more often."""
    index = create_search_index()
    index_document(index, RARE_DOCUMENT_ID, TITLE, VERSION, "alpha alpha beta beta")
    index_document(index, COMMON_DOCUMENT_ID, TITLE, VERSION, "alpha beta beta beta")

    more_occurrences = score_bm25(index, index.documents[RARE_DOCUMENT_ID], ["alpha"])
    fewer_occurrences = score_bm25(index, index.documents[COMMON_DOCUMENT_ID], ["alpha"])

    assert more_occurrences > fewer_occurrences


def test_longer_document_scores_lower_for_same_count() -> None:
    """One occurrence scores lower in a longer document."""
    index = create_search_index()
    index_document(index, SHORT_DOCUMENT_ID, TITLE, VERSION, "alpha beta")
    index_document(index, LONG_DOCUMENT_ID, TITLE, VERSION, "alpha " + "beta " * 20)

    short_score = score_bm25(index, index.documents[SHORT_DOCUMENT_ID], ["alpha"])
    long_score = score_bm25(index, index.documents[LONG_DOCUMENT_ID], ["alpha"])

    assert short_score > long_score


def test_term_in_no_document_adds_nothing() -> None:
    """A term that no document contains adds nothing to the score."""
    index = create_search_index()
    index_document(index, RARE_DOCUMENT_ID, TITLE, VERSION, "alpha beta")

    with_known_term = score_bm25(index, index.documents[RARE_DOCUMENT_ID], ["alpha"])
    with_unknown_term = score_bm25(index, index.documents[RARE_DOCUMENT_ID], ["alpha", "missing"])

    assert with_unknown_term == with_known_term


def test_score_is_zero_when_average_length_is_zero() -> None:
    """A document with no tokens scores zero."""
    index = create_search_index()
    index_document(index, RARE_DOCUMENT_ID, TITLE, VERSION, "...")

    score = score_bm25(index, index.documents[RARE_DOCUMENT_ID], ["alpha"])

    assert score == 0


def test_document_without_query_terms_scores_zero() -> None:
    """A document that contains none of the query terms scores zero."""
    index = create_search_index()
    index_document(index, RARE_DOCUMENT_ID, TITLE, VERSION, "alpha beta")
    index_document(index, COMMON_DOCUMENT_ID, TITLE, VERSION, "gamma delta")

    score = score_bm25(index, index.documents[COMMON_DOCUMENT_ID], ["alpha"])

    assert score == 0
