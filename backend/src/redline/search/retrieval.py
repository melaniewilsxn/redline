from dataclasses import dataclass

from redline.search.index import IndexedDocument
from redline.search.models import IndexedChunk
from redline.search.ranking import score_term
from redline.search.tokenizer import tokenize

STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "any",
        "are",
        "as",
        "at",
        "be",
        "by",
        "clause",
        "for",
        "from",
        "in",
        "into",
        "is",
        "it",
        "its",
        "make",
        "not",
        "of",
        "on",
        "or",
        "other",
        "our",
        "please",
        "section",
        "such",
        "than",
        "that",
        "the",
        "then",
        "these",
        "this",
        "those",
        "to",
        "we",
        "with",
        "you",
        "your",
        "agreement",
    }
)


@dataclass(frozen=True)
class ScoredChunk:
    """A paragraph and its score against an instruction."""

    chunk: IndexedChunk
    score: float


def rank_chunks_for_instruction(
    document: IndexedDocument, instruction: str, limit: int
) -> list[IndexedChunk]:
    """Return the paragraphs that best match the instruction, in document order."""
    terms = content_terms(instruction)
    if not terms:
        return document.chunks[:limit]
    scored = score_matching_chunks(document, terms)
    if not scored:
        return document.chunks[:limit]
    scored.sort(key=lambda scored_chunk: (-scored_chunk.score, scored_chunk.chunk.start))
    chosen = [scored_chunk.chunk for scored_chunk in scored[:limit]]
    chosen.sort(key=lambda chunk: chunk.start)
    return chosen


def content_terms(instruction: str) -> list[str]:
    """Return the instruction's words, without stopwords or duplicates."""
    terms: list[str] = []
    included: set[str] = set()
    for token in tokenize(instruction):
        if token.term in STOPWORDS or token.term in included:
            continue
        included.add(token.term)
        terms.append(token.term)
    return terms


def score_matching_chunks(document: IndexedDocument, terms: list[str]) -> list[ScoredChunk]:
    """Score every paragraph that contains at least one instruction word."""
    if not document.chunks:
        return []
    chunk_count = len(document.chunks)
    average_length = sum(chunk.token_count for chunk in document.chunks) / chunk_count
    containing_counts = count_chunks_containing(document.chunks, terms)
    scored: list[ScoredChunk] = []
    for chunk in document.chunks:
        if not chunk_contains_any(chunk, terms):
            continue
        score = 0.0
        for term in terms:
            if term not in chunk.term_occurrences:
                continue
            score += score_term(
                len(chunk.term_occurrences[term]),
                containing_counts[term],
                chunk_count,
                chunk.token_count,
                average_length,
            )
        scored.append(ScoredChunk(chunk=chunk, score=score))
    return scored


def count_chunks_containing(chunks: list[IndexedChunk], terms: list[str]) -> dict[str, int]:
    """Count how many paragraphs contain each instruction word."""
    counts: dict[str, int] = {}
    for chunk in chunks:
        for term in terms:
            if term not in chunk.term_occurrences:
                continue
            if term in counts:
                counts[term] += 1
            else:
                counts[term] = 1
    return counts


def chunk_contains_any(chunk: IndexedChunk, terms: list[str]) -> bool:
    """Return whether the paragraph contains any of these words."""
    return any(term in chunk.term_occurrences for term in terms)
