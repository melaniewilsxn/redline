from uuid import UUID

from redline.search.index import IndexedDocument, create_search_index, index_document
from redline.search.models import IndexedChunk
from redline.search.retrieval import rank_chunks_for_instruction

DOCUMENT_ID = UUID("00000000-0000-7000-8000-000000000060")
TITLE = "Notes"
VERSION = 1


def test_chunks_with_instruction_terms_rank_first() -> None:
    """The paragraph that contains the instruction word is chosen over an earlier one."""
    document = index_text("The weather is fine.\n\nThe indemnity is one way.\n\n")

    chunks = rank_chunks_for_instruction(document, "indemnity", 1)

    assert len(chunks) == 1
    assert "indemnity" in get_chunk_text(document.text, chunks[0])
    assert chunks[0].start > 0


def test_any_instruction_term_matches() -> None:
    """A paragraph matches when it contains any instruction word."""
    document = index_text("Only alpha is here.\n\nNothing relevant.\n\n")

    chunks = rank_chunks_for_instruction(document, "alpha zebra", 2)

    assert len(chunks) == 1
    assert "alpha" in get_chunk_text(document.text, chunks[0])


def test_stopwords_do_not_match() -> None:
    """Instruction words that are stopwords do not select a paragraph."""
    document = index_text("The indemnity is one way.\n\nThe weather is fine.\n\n")

    chunks = rank_chunks_for_instruction(document, "please make this clause", 1)

    assert chunks[0].start == document.chunks[0].start


def test_results_are_in_document_order() -> None:
    """The chosen paragraphs are returned in document order, not score order."""
    document = index_text("alpha appears once.\n\nalpha alpha alpha appears often.\n\n")

    chunks = rank_chunks_for_instruction(document, "alpha", 2)

    assert len(chunks) == 2
    assert chunks[0].start < chunks[1].start
    assert "once" in get_chunk_text(document.text, chunks[0])


def test_instruction_without_known_terms_returns_first_chunks() -> None:
    """An instruction with no words from the document returns the opening paragraphs."""
    document = index_text("The indemnity is one way.\n\nThe weather is fine.\n\n")

    chunks = rank_chunks_for_instruction(document, "zebra", 1)

    assert chunks[0].start == document.chunks[0].start


def index_text(text: str) -> IndexedDocument:
    """Index one document and return it."""
    index = create_search_index()
    index_document(index, DOCUMENT_ID, TITLE, VERSION, text)
    return index.documents[DOCUMENT_ID]


def get_chunk_text(text: str, chunk: IndexedChunk) -> str:
    """Return the document text covered by a chunk."""
    return text[chunk.start : chunk.start + chunk.length]
