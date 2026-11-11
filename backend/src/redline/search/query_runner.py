import logging
from dataclasses import dataclass
from uuid import UUID

from redline.search.errors import DocumentNotIndexedError, SearchError
from redline.search.index import (
    MAXIMUM_PREFIX_EXPANSIONS,
    IndexedDocument,
    SearchIndex,
    find_terms_with_prefix,
)
from redline.search.models import (
    AllDocuments,
    SearchHit,
    SearchPage,
    SearchQuery,
    SearchScope,
    SelectedDocuments,
)
from redline.search.ranking import score_bm25
from redline.search.snippets import (
    MAXIMUM_SNIPPETS_PER_HIT,
    build_snippet,
    find_chunk_highlights,
    find_phrase_spans,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScoredDocument:
    """A matching document with its score, before snippets are built."""

    document: IndexedDocument
    score: float
    match_count: int


def run_query(
    index: SearchIndex, query: SearchQuery, scope: SearchScope, limit: int, offset: int
) -> SearchPage:
    """Return one page of documents that contain every term and every phrase."""
    expansions = expand_prefix_terms(index, query)
    if query.prefix_terms and not expansions:
        return SearchPage(hits=[], total_count=0)
    terms = collect_query_terms(query)
    matched = [
        document
        for document in find_candidates(index, query, scope, expansions)
        if document_matches_phrases(document, query)
    ]
    scored = [score_document(index, document, query, terms, expansions) for document in matched]
    scored.sort(
        key=lambda scored_document: (-scored_document.score, scored_document.document.document_id)
    )
    total_count = len(scored)
    page = scored[offset : offset + limit]
    hits = [build_hit(scored_document, query, expansions) for scored_document in page]
    return SearchPage(hits=hits, total_count=total_count)


def expand_prefix_terms(index: SearchIndex, query: SearchQuery) -> list[str]:
    """Return the vocabulary words for each prefix, most widespread first."""
    expansions: list[str] = []
    seen: set[str] = set()
    for prefix in query.prefix_terms:
        for term in find_terms_with_prefix(index, prefix, MAXIMUM_PREFIX_EXPANSIONS):
            if term in seen:
                continue
            seen.add(term)
            expansions.append(term)
    return expansions


def collect_query_terms(query: SearchQuery) -> list[str]:
    """Return unquoted terms and phrase terms, in first-seen order, without duplicates."""
    seen: set[str] = set()
    terms: list[str] = []
    for term in query.terms:
        if term in seen:
            continue
        seen.add(term)
        terms.append(term)
    for phrase in query.phrases:
        for term in phrase.terms:
            if term in seen:
                continue
            seen.add(term)
            terms.append(term)
    return terms


def find_candidates(
    index: SearchIndex, query: SearchQuery, scope: SearchScope, expansions: list[str]
) -> list[IndexedDocument]:
    """Return documents in scope that contain every required term, starting from the rarest."""
    allowed = document_ids_in_scope(index, scope)
    if not allowed:
        return []
    matched = allowed
    if query.prefix_terms:
        prefix_documents: set[UUID] = set()
        for term in expansions:
            prefix_documents |= index.term_documents[term]
        matched = matched & prefix_documents
        if not matched:
            return []
    terms = collect_query_terms(query)
    if not terms:
        return [index.documents[document_id] for document_id in matched]
    ordered_terms = sorted(terms, key=lambda term: containing_document_count(index, term))
    for term in ordered_terms:
        if term not in index.term_documents:
            return []
        matched = matched & index.term_documents[term]
        if not matched:
            return []
    return [index.documents[document_id] for document_id in matched]


def document_ids_in_scope(index: SearchIndex, scope: SearchScope) -> set[UUID]:
    """Return the document ids the scope allows. An unknown selected id is an error."""
    match scope:
        case SelectedDocuments(document_ids=document_ids):
            selected: set[UUID] = set()
            for document_id in document_ids:
                if document_id not in index.documents:
                    raise DocumentNotIndexedError(document_id)
                selected.add(document_id)
            return selected
        case AllDocuments():
            return set(index.documents)
        case _:
            scope_name = type(scope).__name__
            logger.error(f"Unknown search scope {scope_name}")
            raise SearchError(f"Unknown search scope {scope_name}")


def containing_document_count(index: SearchIndex, term: str) -> int:
    """Return how many documents contain term."""
    if term not in index.term_documents:
        return 0
    return len(index.term_documents[term])


def document_matches_phrases(document: IndexedDocument, query: SearchQuery) -> bool:
    """Return whether every phrase occurs inside at least one chunk."""
    for phrase in query.phrases:
        found = False
        for chunk in document.chunks:
            if find_phrase_spans(chunk, phrase):
                found = True
                break
        if not found:
            return False
    return True


def score_document(
    index: SearchIndex,
    document: IndexedDocument,
    query: SearchQuery,
    terms: list[str],
    expansions: list[str],
) -> ScoredDocument:
    """Score one matching document and count its term and phrase occurrences."""
    match_count = 0
    counted = set(query.terms)
    for term in query.terms:
        if term in document.term_counts:
            match_count += document.term_counts[term]
    for term in expansions:
        if term in counted or term not in document.term_counts:
            continue
        counted.add(term)
        match_count += document.term_counts[term]
    for phrase in query.phrases:
        for chunk in document.chunks:
            match_count += len(find_phrase_spans(chunk, phrase))
    score_terms = list(terms)
    seen = set(score_terms)
    for term in expansions:
        if term in seen or term not in document.term_counts:
            continue
        seen.add(term)
        score_terms.append(term)
    return ScoredDocument(
        document=document,
        score=score_bm25(index, document, score_terms),
        match_count=match_count,
    )


def build_hit(
    scored_document: ScoredDocument, query: SearchQuery, expansions: list[str]
) -> SearchHit:
    """Build a hit from the first matching chunks in document order."""
    document = scored_document.document
    highlight_query = get_query_with_expansions(query, expansions)
    snippets = []
    for chunk in document.chunks:
        highlights = find_chunk_highlights(chunk, highlight_query)
        if not highlights:
            continue
        snippets.append(build_snippet(document.text, chunk, highlights))
        if len(snippets) == MAXIMUM_SNIPPETS_PER_HIT:
            break
    return SearchHit(
        document_id=document.document_id,
        title=document.title,
        version=document.version,
        score=scored_document.score,
        match_count=scored_document.match_count,
        snippets=snippets,
    )


def get_query_with_expansions(query: SearchQuery, expansions: list[str]) -> SearchQuery:
    """Return a query whose terms include each prefix expansion, so highlights cover them."""
    terms = list(query.terms)
    seen = set(terms)
    for term in expansions:
        if term in seen:
            continue
        seen.add(term)
        terms.append(term)
    return SearchQuery(terms=terms, phrases=query.phrases, prefix_terms=[])
