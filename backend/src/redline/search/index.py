import logging
from dataclasses import dataclass
from uuid import UUID

from redline.editing.models import AppliedEdit, TextSpan
from redline.search.chunker import split_into_chunks
from redline.search.errors import DocumentNotIndexedError
from redline.search.models import IndexedChunk, TokenOccurrence
from redline.search.tokenizer import tokenize

logger = logging.getLogger(__name__)


@dataclass
class IndexedDocument:
    """One document's chunks and term counts."""

    document_id: UUID
    title: str
    version: int
    text: str
    chunks: list[IndexedChunk]
    term_counts: dict[str, int]
    token_count: int


@dataclass
class SearchIndex:
    """Every indexed document, and which documents contain each term."""

    documents: dict[UUID, IndexedDocument]
    term_documents: dict[str, set[UUID]]


@dataclass(frozen=True)
class ChunkRun:
    """Consecutive chunks that are rebuilt together."""

    first_index: int
    last_index: int


def create_search_index() -> SearchIndex:
    """Return an empty index."""
    return SearchIndex(documents={}, term_documents={})


def index_chunk(text: str, span: TextSpan) -> IndexedChunk:
    """Tokenize one slice. Positions start at 0 and spans are relative to the slice."""
    tokens = tokenize(text[span.start : span.end])
    term_occurrences: dict[str, list[TokenOccurrence]] = {}
    for position, token in enumerate(tokens):
        occurrence = TokenOccurrence(position=position, span=token.span)
        if token.term not in term_occurrences:
            term_occurrences[token.term] = []
        term_occurrences[token.term].append(occurrence)
    return IndexedChunk(
        start=span.start,
        length=span.end - span.start,
        token_count=len(tokens),
        term_occurrences=term_occurrences,
    )


def index_document(
    index: SearchIndex, document_id: UUID, title: str, version: int, text: str
) -> None:
    """Chunk and index the whole text, replacing any earlier entry for this document."""
    chunks = [index_chunk(text, span) for span in split_into_chunks(text, 0)]
    term_counts, token_count = count_terms(chunks)
    replacement = IndexedDocument(
        document_id=document_id,
        title=title,
        version=version,
        text=text,
        chunks=chunks,
        term_counts=term_counts,
        token_count=token_count,
    )
    if document_id in index.documents:
        remove_document_terms(index, index.documents[document_id])
    index.documents[document_id] = replacement
    add_document_terms(index, replacement)


def update_indexed_document(
    index: SearchIndex,
    document_id: UUID,
    version: int,
    text: str,
    applied_edits: list[AppliedEdit],
) -> None:
    """Rebuild the chunks an edit touches, then swap in the replacement document."""
    if document_id not in index.documents:
        raise DocumentNotIndexedError(document_id)
    previous = index.documents[document_id]
    if previous.chunks:
        chunks = rebuild_changed_chunks(previous, text, applied_edits)
    else:
        chunks = [index_chunk(text, span) for span in split_into_chunks(text, 0)]
    term_counts, token_count = count_terms(chunks)
    replacement = IndexedDocument(
        document_id=document_id,
        title=previous.title,
        version=version,
        text=text,
        chunks=chunks,
        term_counts=term_counts,
        token_count=token_count,
    )
    index.documents[document_id] = replacement
    update_term_documents(index, previous, replacement)


def remove_document_terms(index: SearchIndex, document: IndexedDocument) -> None:
    """Take a document's terms out of the term map."""
    for term in document.term_counts:
        if term not in index.term_documents:
            continue
        index.term_documents[term].discard(document.document_id)
        if not index.term_documents[term]:
            del index.term_documents[term]


def add_document_terms(index: SearchIndex, document: IndexedDocument) -> None:
    """Record that this document contains each of its terms."""
    for term, count in document.term_counts.items():
        if count == 0:
            continue
        if term not in index.term_documents:
            index.term_documents[term] = set()
        index.term_documents[term].add(document.document_id)


def count_terms(chunks: list[IndexedChunk]) -> tuple[dict[str, int], int]:
    """Return how often each term occurs, and the total number of tokens."""
    term_counts: dict[str, int] = {}
    token_count = 0
    for chunk in chunks:
        token_count += chunk.token_count
        for term, occurrences in chunk.term_occurrences.items():
            if term not in term_counts:
                term_counts[term] = 0
            term_counts[term] += len(occurrences)
    return term_counts, token_count


def rebuild_changed_chunks(
    document: IndexedDocument, text: str, applied_edits: list[AppliedEdit]
) -> list[IndexedChunk]:
    """Rebuild the runs an edit touches, and shift the chunks it does not."""
    runs = find_chunk_runs(document.chunks, applied_edits)
    assigned = assign_edits(document, runs, applied_edits)
    chunks: list[IndexedChunk] = []
    shift = 0
    run_number = 0
    chunk_index = 0
    while chunk_index < len(document.chunks):
        if run_number < len(runs) and chunk_index == runs[run_number].first_index:
            run = runs[run_number]
            run_change = sum(edit.length_change for edit in assigned[run_number])
            run_start = document.chunks[run.first_index].start
            last_chunk = document.chunks[run.last_index]
            run_end = last_chunk.start + last_chunk.length
            new_start = run_start + shift
            new_end = run_end + shift + run_change
            region = text[new_start:new_end]
            chunks.extend(index_chunk(text, span) for span in split_into_chunks(region, new_start))
            shift += run_change
            chunk_index = run.last_index + 1
            run_number += 1
            continue
        chunks.append(shift_chunk(document.chunks[chunk_index], shift))
        chunk_index += 1
    return chunks


def find_chunk_runs(chunks: list[IndexedChunk], applied_edits: list[AppliedEdit]) -> list[ChunkRun]:
    """Group touched chunks, plus one neighbor on each side, into consecutive runs."""
    touched: set[int] = set()
    for index, chunk in enumerate(chunks):
        chunk_end = chunk.start + chunk.length
        for edit in applied_edits:
            if edit_touches_span(edit, chunk.start, chunk_end):
                touched.add(index)
                break
    expanded: set[int] = set()
    for index in touched:
        expanded.add(index)
        if index > 0:
            expanded.add(index - 1)
        if index + 1 < len(chunks):
            expanded.add(index + 1)
    return group_consecutive_indexes(sorted(expanded))


def group_consecutive_indexes(indexes: list[int]) -> list[ChunkRun]:
    """Group sorted chunk indexes that sit next to each other."""
    if not indexes:
        return []
    runs: list[ChunkRun] = []
    first_index = indexes[0]
    last_index = indexes[0]
    for index in indexes[1:]:
        if index == last_index + 1:
            last_index = index
            continue
        runs.append(ChunkRun(first_index=first_index, last_index=last_index))
        first_index = index
        last_index = index
    runs.append(ChunkRun(first_index=first_index, last_index=last_index))
    return runs


def assign_edits(
    document: IndexedDocument, runs: list[ChunkRun], applied_edits: list[AppliedEdit]
) -> list[list[AppliedEdit]]:
    """Give each edit to the one run it overlaps, or whose edge its insert sits on."""
    assigned: list[list[AppliedEdit]] = []
    used: set[int] = set()
    for run in runs:
        run_start = document.chunks[run.first_index].start
        last_chunk = document.chunks[run.last_index]
        run_end = last_chunk.start + last_chunk.length
        run_edits: list[AppliedEdit] = []
        for edit_index, edit in enumerate(applied_edits):
            if edit_index in used:
                continue
            if edit_touches_span(edit, run_start, run_end):
                run_edits.append(edit)
                used.add(edit_index)
        assigned.append(run_edits)
    if len(used) != len(applied_edits):
        logger.error(
            f"Edit was not assigned to a run for document {document.document_id} "
            f"at version {document.version}, {len(applied_edits)} edits, {len(used)} assigned"
        )
        raise RuntimeError("Edit was not assigned to a run")
    return assigned


def edit_touches_span(edit: AppliedEdit, span_start: int, span_end: int) -> bool:
    """Return whether the edit overlaps the span, or is an insert on either edge."""
    if edit.span.start == edit.span.end:
        return span_start <= edit.span.start <= span_end
    return edit.span.start < span_end and span_start < edit.span.end


def shift_chunk(chunk: IndexedChunk, shift: int) -> IndexedChunk:
    """Return the chunk moved by shift characters. Relative spans stay as they are."""
    if shift == 0:
        return chunk
    return IndexedChunk(
        start=chunk.start + shift,
        length=chunk.length,
        token_count=chunk.token_count,
        term_occurrences=chunk.term_occurrences,
    )


def update_term_documents(
    index: SearchIndex, previous: IndexedDocument, replacement: IndexedDocument
) -> None:
    """Add or drop this document for terms whose count crossed zero."""
    for term, count in previous.term_counts.items():
        replacement_count = 0
        if term in replacement.term_counts:
            replacement_count = replacement.term_counts[term]
        if count > 0 and replacement_count == 0 and term in index.term_documents:
            index.term_documents[term].discard(previous.document_id)
            if not index.term_documents[term]:
                del index.term_documents[term]
    for term, count in replacement.term_counts.items():
        previous_count = 0
        if term in previous.term_counts:
            previous_count = previous.term_counts[term]
        if previous_count == 0 and count > 0:
            if term not in index.term_documents:
                index.term_documents[term] = set()
            index.term_documents[term].add(replacement.document_id)
