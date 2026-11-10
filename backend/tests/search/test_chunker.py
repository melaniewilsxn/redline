from redline.search.chunker import MAXIMUM_CHUNK_CHARACTERS, split_into_chunks


def test_chunks_tile_the_text_exactly() -> None:
    """The spans join back to the full text, with no gaps."""
    text = "Alpha.\n\nBeta stays on one line.\n\nGamma."

    spans = split_into_chunks(text, 0)

    assert "".join(text[span.start : span.end] for span in spans) == text
    assert [span.end for span in spans[:-1]] == [span.start for span in spans[1:]]


def test_blank_line_separates_paragraphs() -> None:
    """A blank line starts a new chunk, and the blank line stays with the paragraph before it."""
    text = "Alpha.\n\nBeta."

    spans = split_into_chunks(text, 0)

    assert len(spans) == 2
    assert text[spans[0].start : spans[0].end] == "Alpha.\n\n"
    assert text[spans[1].start : spans[1].end] == "Beta."


def test_single_newline_does_not_split() -> None:
    """One newline is not a paragraph break."""
    text = "Alpha.\nBeta."

    spans = split_into_chunks(text, 0)

    assert len(spans) == 1
    assert text[spans[0].start : spans[0].end] == text


def test_long_paragraph_splits_at_whitespace_before_limit() -> None:
    """A long paragraph splits at the last whitespace before the limit."""
    text = "abcdefghi " * 500

    spans = split_into_chunks(text, 0)

    assert "".join(text[span.start : span.end] for span in spans) == text
    assert spans[0].end - spans[0].start <= MAXIMUM_CHUNK_CHARACTERS
    assert text[spans[1].start].isspace()


def test_long_paragraph_without_whitespace_splits_at_limit() -> None:
    """A long word splits at the character limit."""
    text = "a" * (MAXIMUM_CHUNK_CHARACTERS + 10)

    spans = split_into_chunks(text, 0)

    assert spans[0].end - spans[0].start == MAXIMUM_CHUNK_CHARACTERS
    assert spans[1].start == MAXIMUM_CHUNK_CHARACTERS
    assert "".join(text[span.start : span.end] for span in spans) == text


def test_offset_shifts_every_span() -> None:
    """Offset is added to every span."""
    offset = 25

    spans = split_into_chunks("Alpha.\n\nBeta.", offset)

    assert spans[0].start == offset
    assert spans[1].start > offset


def test_empty_text_has_no_chunks() -> None:
    """Empty text has no spans."""
    spans = split_into_chunks("", 0)

    assert spans == []
