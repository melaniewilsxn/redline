from redline.editing.models import TextSpan
from redline.search.models import IndexedChunk, SearchPhrase, SearchQuery, Snippet

MAXIMUM_SNIPPETS_PER_HIT = 3
SNIPPET_LEADING_CHARACTERS = 80
SNIPPET_MAXIMUM_CHARACTERS = 240
WORD_PUNCTUATION = "-'’_"  # noqa: RUF001


def find_chunk_highlights(chunk: IndexedChunk, query: SearchQuery) -> list[TextSpan]:
    """Return absolute spans of the query's terms and phrases in this chunk, merged."""
    highlights: list[TextSpan] = []
    for term in query.terms:
        if term not in chunk.term_occurrences:
            continue
        for occurrence in chunk.term_occurrences[term]:
            highlights.append(
                TextSpan(
                    start=chunk.start + occurrence.span.start,
                    end=chunk.start + occurrence.span.end,
                )
            )
    for phrase in query.phrases:
        highlights.extend(find_phrase_spans(chunk, phrase))
    highlights.sort(key=lambda span: (span.start, span.end))
    return merge_highlights(highlights)


def find_phrase_spans(chunk: IndexedChunk, phrase: SearchPhrase) -> list[TextSpan]:
    """Return absolute spans of this phrase where its words sit in consecutive positions."""
    if not phrase.terms:
        return []
    first_term = phrase.terms[0]
    if first_term not in chunk.term_occurrences:
        return []
    position_terms: dict[int, str] = {}
    position_spans: dict[int, TextSpan] = {}
    for term, occurrences in chunk.term_occurrences.items():
        for occurrence in occurrences:
            position_terms[occurrence.position] = term
            position_spans[occurrence.position] = occurrence.span
    spans: list[TextSpan] = []
    phrase_length = len(phrase.terms)
    for occurrence in chunk.term_occurrences[first_term]:
        start_position = occurrence.position
        if not phrase_starts_at(position_terms, phrase, start_position):
            continue
        last_position = start_position + phrase_length - 1
        spans.append(
            TextSpan(
                start=chunk.start + position_spans[start_position].start,
                end=chunk.start + position_spans[last_position].end,
            )
        )
    return spans


def phrase_starts_at(
    position_terms: dict[int, str], phrase: SearchPhrase, start_position: int
) -> bool:
    """Return whether the phrase's terms occupy the positions starting here."""
    for offset, term in enumerate(phrase.terms):
        position = start_position + offset
        if position not in position_terms or position_terms[position] != term:
            return False
    return True


def merge_highlights(spans: list[TextSpan]) -> list[TextSpan]:
    """Merge spans that overlap. The list is already sorted by start."""
    if not spans:
        return []
    merged: list[TextSpan] = [spans[0]]
    for span in spans[1:]:
        current = merged[-1]
        if span.start < current.end:
            merged[-1] = TextSpan(start=current.start, end=max(current.end, span.end))
            continue
        merged.append(span)
    return merged


def build_snippet(text: str, chunk: IndexedChunk, highlights: list[TextSpan]) -> Snippet:
    """Return a short window around the first highlight, inside this chunk."""
    content_start = chunk.start
    content_end = clip_trailing_space(text, chunk)
    for highlight in highlights:
        if highlight.end > content_end:
            content_end = highlight.end
    first = highlights[0]
    if first.end - first.start > SNIPPET_MAXIMUM_CHARACTERS:
        window_start = first.start
        window_end = first.end
    else:
        window_start = first.start - SNIPPET_LEADING_CHARACTERS
        if window_start < content_start:
            window_start = content_start
        window_end = window_start + SNIPPET_MAXIMUM_CHARACTERS
        if window_end > content_end:
            window_end = content_end
        if window_end < first.end:
            window_end = first.end
            window_start = window_end - SNIPPET_MAXIMUM_CHARACTERS
            if window_start < content_start:
                window_start = content_start
        if window_start > first.start:
            window_start = first.start
    window_start, window_end = move_edges_to_whitespace(
        text, window_start, window_end, content_start, content_end, highlights
    )
    kept = [
        highlight
        for highlight in highlights
        if highlight.start >= window_start and highlight.end <= window_end
    ]
    return Snippet(
        span=TextSpan(start=window_start, end=window_end),
        text=text[window_start:window_end],
        highlights=kept,
    )


def clip_trailing_space(text: str, chunk: IndexedChunk) -> int:
    """Return the chunk end with its trailing blank lines removed."""
    end = chunk.start + chunk.length
    while end > chunk.start and text[end - 1].isspace():
        end -= 1
    return end


def move_edges_to_whitespace(
    text: str,
    window_start: int,
    window_end: int,
    content_start: int,
    content_end: int,
    highlights: list[TextSpan],
) -> tuple[int, int]:
    """Move the window edges off the middle of a word without cutting a highlight."""
    while window_start > content_start and cuts_word(text, window_start):
        window_start -= 1
    while window_end < content_end and cuts_word(text, window_end):
        window_end += 1
    for highlight in highlights:
        if highlight.start < window_start < highlight.end:
            window_start = highlight.start
        if highlight.start < window_end < highlight.end:
            window_end = highlight.end
    return window_start, window_end


def cuts_word(text: str, index: int) -> bool:
    """Return whether index falls between two characters of one word."""
    if index <= 0 or index >= len(text):
        return False
    return is_word_character(text[index - 1]) and is_word_character(text[index])


def is_word_character(character: str) -> bool:
    """Return whether a word token can contain this character."""
    return character.isalnum() or character in WORD_PUNCTUATION
