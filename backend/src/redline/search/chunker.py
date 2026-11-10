import re

from redline.editing.models import TextSpan

PARAGRAPH_BREAK_PATTERN = re.compile(r"\n[ \t]*\n\s*")
MAXIMUM_CHUNK_CHARACTERS = 4000


def split_into_chunks(text: str, offset: int) -> list[TextSpan]:
    """Split text into paragraph spans that tile it, then add offset to each span."""
    if text == "":
        return []
    spans: list[TextSpan] = []
    cursor = 0
    text_length = len(text)
    while cursor < text_length:
        break_match = PARAGRAPH_BREAK_PATTERN.search(text, cursor)
        if break_match is None:
            paragraph_end = text_length
            region_end = text_length
        else:
            paragraph_end = break_match.start()
            region_end = break_match.end()
        spans.extend(split_paragraph(text, cursor, paragraph_end, region_end, offset))
        cursor = region_end
    return spans


def split_paragraph(
    text: str, start: int, paragraph_end: int, region_end: int, offset: int
) -> list[TextSpan]:
    """Split one paragraph. The blank lines after it stay on the last piece."""
    if paragraph_end == start:
        return [TextSpan(start=offset + start, end=offset + region_end)]
    spans: list[TextSpan] = []
    piece_start = start
    while piece_start < paragraph_end:
        remaining = paragraph_end - piece_start
        if remaining <= MAXIMUM_CHUNK_CHARACTERS:
            spans.append(TextSpan(start=offset + piece_start, end=offset + region_end))
            break
        split_at = find_split_offset(text, piece_start, piece_start + MAXIMUM_CHUNK_CHARACTERS)
        spans.append(TextSpan(start=offset + piece_start, end=offset + split_at))
        piece_start = split_at
    return spans


def find_split_offset(text: str, start: int, limit: int) -> int:
    """Return the last whitespace before limit, which starts the next span."""
    last_whitespace = start
    for index in range(start, limit):
        if text[index].isspace():
            last_whitespace = index
    if last_whitespace == start:
        return limit
    return last_whitespace
