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
        inverse_document_frequency = math.log(
            1
            + (document_count - containing_document_count + 0.5) / (containing_document_count + 0.5)
        )
        if term in document.term_counts:  # noqa: SIM108
            term_frequency = document.term_counts[term]
        else:
            term_frequency = 0
        numerator = inverse_document_frequency * term_frequency * (BM25_K1 + 1)
        denominator = term_frequency + BM25_K1 * (
            1 - BM25_B + BM25_B * document_length / average_document_length
        )
        score += numerator / denominator
    return score
