import math

from redline.search.index import IndexedDocument, SearchIndex

BM25_K1 = 1.2
BM25_B = 0.75


def score_bm25(index: SearchIndex, document: IndexedDocument, terms: list[str]) -> float:
    """Score one document for these terms. A term it does not contain adds nothing."""
    if not index.documents:
        return 0.0
    average_document_length = sum(
        indexed.token_count for indexed in index.documents.values()
    ) / len(index.documents)
    if average_document_length == 0:
        return 0.0
    document_count = len(index.documents)
    document_length = document.token_count
    score = 0.0
    for term in terms:
        if term in index.term_documents:
            containing_document_count = len(index.term_documents[term])
        else:
            containing_document_count = 0
        if term in document.term_counts:  # noqa: SIM108
            term_frequency = document.term_counts[term]
        else:
            term_frequency = 0
        score += score_term(
            term_frequency,
            containing_document_count,
            document_count,
            document_length,
            average_document_length,
        )
    return score


def score_term(
    term_frequency: int,
    containing_count: int,
    collection_count: int,
    length: int,
    average_length: float,
) -> float:
    """Return one term's BM25 weight. A missing term or an empty collection adds nothing."""
    if average_length == 0:
        return 0.0
    inverse_document_frequency = math.log(
        1 + (collection_count - containing_count + 0.5) / (containing_count + 0.5)
    )
    numerator = inverse_document_frequency * term_frequency * (BM25_K1 + 1)
    denominator = term_frequency + BM25_K1 * (1 - BM25_B + BM25_B * length / average_length)
    return numerator / denominator
