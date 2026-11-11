from uuid import UUID

from redline.search.index import IndexedDocument, create_search_index, index_document
from redline.search.models import SearchPhrase, SearchQuery
from redline.search.snippets import (
    SNIPPET_MAXIMUM_CHARACTERS,
    build_snippet,
    find_chunk_highlights,
    find_phrase_spans,
)

DOCUMENT_ID = UUID("00000000-0000-7000-8000-000000000030")
TITLE = "Notes"
VERSION = 1


def test_term_highlights_are_absolute_offsets() -> None:
    """A term highlight uses offsets in the whole document."""
    text = "Hello alpha."
    chunk = index_one(text).chunks[0]
    query = SearchQuery(terms=["alpha"], phrases=[], prefix_terms=[])

    highlights = find_chunk_highlights(chunk, query)

    assert len(highlights) == 1
    assert text[highlights[0].start : highlights[0].end] == "alpha"


def test_chunk_missing_a_phrase_term_has_no_phrase_spans() -> None:
    """A phrase is absent when the chunk is missing one of its words."""
    text = "Please send written today."
    chunk = index_one(text).chunks[0]
    phrase = SearchPhrase(terms=["written", "notice"])

    spans = find_phrase_spans(chunk, phrase)

    assert spans == []


def test_phrase_highlight_spans_the_whole_phrase() -> None:
    """A phrase highlight runs from the first word to the last."""
    text = "Please send written notice today."
    chunk = index_one(text).chunks[0]
    phrase = SearchPhrase(terms=["written", "notice"])

    spans = find_phrase_spans(chunk, phrase)

    assert len(spans) == 1
    assert text[spans[0].start : spans[0].end] == "written notice"


def test_phrase_terms_out_of_order_do_not_highlight() -> None:
    """A phrase does not match when its words are in the other order."""
    text = "Please send written notice today."
    chunk = index_one(text).chunks[0]
    phrase = SearchPhrase(terms=["notice", "written"])

    spans = find_phrase_spans(chunk, phrase)

    assert spans == []


def test_overlapping_highlights_are_merged() -> None:
    """A term inside a phrase is merged into the phrase span."""
    text = "Please send written notice today."
    chunk = index_one(text).chunks[0]
    query = SearchQuery(
        terms=["notice"],
        phrases=[SearchPhrase(terms=["written", "notice"])],
        prefix_terms=[],
    )

    highlights = find_chunk_highlights(chunk, query)

    assert len(highlights) == 1
    assert text[highlights[0].start : highlights[0].end] == "written notice"


def test_snippet_does_not_cut_a_highlight() -> None:
    """A highlight longer than the window is kept whole."""
    word = "x" * (SNIPPET_MAXIMUM_CHARACTERS + 20)
    text = f"before {word} after"
    document = index_one(text)
    highlights = find_chunk_highlights(
        document.chunks[0], SearchQuery(terms=[word], phrases=[], prefix_terms=[])
    )

    snippet = build_snippet(text, document.chunks[0], highlights)

    assert highlights[0].start >= snippet.span.start
    assert highlights[0].end <= snippet.span.end
    assert (
        snippet.text[
            highlights[0].start - snippet.span.start : highlights[0].end - snippet.span.start
        ]
        == word
    )


def test_snippet_stays_inside_its_chunk() -> None:
    """A snippet for a later paragraph does not include the paragraph before it."""
    text = "Alpha is here.\n\n" + ("beta " * 30)
    document = index_one(text)
    query = SearchQuery(terms=["beta"], phrases=[], prefix_terms=[])
    beta_chunk = document.chunks[1]
    highlights = find_chunk_highlights(beta_chunk, query)

    snippet = build_snippet(text, beta_chunk, highlights)

    assert snippet.span.start >= beta_chunk.start
    assert snippet.span.end <= beta_chunk.start + beta_chunk.length
    assert "Alpha" not in snippet.text
    assert "\n\n" not in snippet.text


def index_one(text: str) -> IndexedDocument:
    """Index one document and return it."""
    index = create_search_index()
    index_document(index, DOCUMENT_ID, TITLE, VERSION, text)
    return index.documents[DOCUMENT_ID]
