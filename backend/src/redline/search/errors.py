from uuid import UUID

EMPTY_QUERY_MESSAGE = "Query has no words"


class SearchError(Exception):
    """A search failure the API can map to a response."""


class EmptyQueryError(SearchError):
    """The query has no words."""

    def __init__(self) -> None:
        """Build the error."""
        super().__init__(EMPTY_QUERY_MESSAGE)


class DocumentNotIndexedError(SearchError):
    """A selected document is not in the index."""

    def __init__(self, document_id: UUID) -> None:
        """Build the error for one document."""
        self.document_id = document_id
        super().__init__(f"Document {document_id} is not indexed")
