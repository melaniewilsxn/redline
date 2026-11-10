import logging
import threading
import time
from enum import StrEnum

from redline.editing.models import AppliedEdit, TextSpan
from redline.search.index import (
    SearchIndex,
    create_search_index,
    index_document,
    update_indexed_document,
)
from redline.search.models import SearchPage, SearchScope
from redline.search.query_parser import parse_query
from redline.search.query_runner import run_query
from redline.search.retrieval import rank_chunks_for_instruction
from redline.storage.models import StoredDocument

logger = logging.getLogger(__name__)


class IndexUpdatePath(StrEnum):
    """How an indexed document was brought up to the committed text."""

    INCREMENTAL = "incremental"
    FULL = "full"


class SearchService:
    """Owns the live index and keeps it consistent with committed writes."""

    def __init__(self) -> None:
        """Start with an empty index and a lock around it."""
        self.index: SearchIndex = create_search_index()
        self.lock = threading.Lock()

    def load_documents(self, documents: list[StoredDocument]) -> None:
        """Index every document. Used when the process starts."""
        logger.info(f"Started loading {len(documents)} documents into the search index")
        started = time.perf_counter()
        with self.lock:
            for document in documents:
                index_document(
                    self.index,
                    document.id,
                    document.title,
                    document.version,
                    document.text,
                )
        elapsed = time.perf_counter() - started
        logger.info(
            f"Finished loading {len(documents)} documents into the search index "
            f"in {elapsed:.3f} seconds"
        )

    def add_document(self, document: StoredDocument) -> None:
        """Index a new document. A failure is logged and does not fail the request."""
        logger.info(
            f"Started indexing document {document.id} at version {document.version}, "
            f"length {len(document.text)}"
        )
        try:
            with self.lock:
                index_document(
                    self.index,
                    document.id,
                    document.title,
                    document.version,
                    document.text,
                )
        except Exception:
            logger.exception(
                f"Failed to index document {document.id} at version {document.version}, "
                f"length {len(document.text)}"
            )
            return
        logger.info(
            f"Finished indexing document {document.id} at version {document.version}, "
            f"length {len(document.text)}"
        )

    def update_document(
        self, document: StoredDocument, applied_edits: list[AppliedEdit], base_version: int
    ) -> None:
        """Update one document after a committed edit. The request still succeeds if this fails."""
        logger.info(
            f"Started updating document {document.id} from version {base_version} "
            f"to version {document.version}, {len(applied_edits)} edits"
        )
        path = IndexUpdatePath.FULL
        try:
            with self.lock:
                path = update_locked_document(self.index, document, applied_edits, base_version)
        except Exception:
            logger.exception(
                f"Failed to reindex document {document.id} at version {document.version}"
            )
            return
        logger.info(
            f"Finished updating document {document.id} at version {document.version} "
            f"by {path.value}, from version {base_version}"
        )

    def search(self, query_text: str, scope: SearchScope, limit: int, offset: int) -> SearchPage:
        """Parse the query and return one page of hits."""
        query = parse_query(query_text)
        scope_name = type(scope).__name__
        logger.info(
            f"Started search with {len(query.terms)} terms and {len(query.phrases)} phrases "
            f"over {scope_name}, limit {limit}, offset {offset}"
        )
        with self.lock:
            page = run_query(self.index, query, scope, limit, offset)
        logger.info(
            f"Finished search with {len(query.terms)} terms and {len(query.phrases)} phrases "
            f"over {scope_name}, {page.total_count} hits"
        )
        return page

    def find_relevant_spans(
        self, document: StoredDocument, instruction: str, limit: int
    ) -> list[TextSpan]:
        """Return paragraph spans for an instruction, refreshing a stale index entry first."""
        logger.info(
            f"Started choosing spans for document {document.id} version {document.version}, "
            f"instruction length {len(instruction)}, limit {limit}"
        )
        with self.lock:
            if (
                document.id not in self.index.documents
                or self.index.documents[document.id].version != document.version
            ):
                index_document(
                    self.index, document.id, document.title, document.version, document.text
                )
            chunks = rank_chunks_for_instruction(
                self.index.documents[document.id], instruction, limit
            )
        spans = [TextSpan(start=chunk.start, end=chunk.start + chunk.length) for chunk in chunks]
        logger.info(
            f"Finished choosing {len(spans)} spans for document {document.id} "
            f"version {document.version}"
        )
        return spans


def update_locked_document(
    index: SearchIndex,
    document: StoredDocument,
    applied_edits: list[AppliedEdit],
    base_version: int,
) -> IndexUpdatePath:
    """Update a document the caller already holds the index lock for."""
    if document.id in index.documents and index.documents[document.id].version == base_version:
        try:
            update_indexed_document(
                index, document.id, document.version, document.text, applied_edits
            )
        except Exception:
            logger.exception(
                f"Incremental update failed for document {document.id} "
                f"at version {document.version}, base version {base_version}"
            )
            index_document(index, document.id, document.title, document.version, document.text)
            return IndexUpdatePath.FULL
        return IndexUpdatePath.INCREMENTAL
    if document.id in index.documents:
        indexed_version = index.documents[document.id].version
        logger.warning(
            f"Document {document.id} is at version {indexed_version}, "
            f"not base version {base_version}"
        )
    else:
        logger.warning(f"Document {document.id} is not in the index at base version {base_version}")
    index_document(index, document.id, document.title, document.version, document.text)
    return IndexUpdatePath.FULL
