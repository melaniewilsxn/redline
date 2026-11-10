from uuid import UUID


class StorageError(Exception):
    """Base class for storage failures."""


class DocumentNotFoundError(StorageError):
    """No document exists with this id."""

    def __init__(self, document_id: UUID) -> None:
        """Store the document id and build a readable message."""
        self.document_id = document_id
        super().__init__(f"Document {document_id} was not found")


class DocumentVersionNotFoundError(StorageError):
    """This document has no version with this number."""

    def __init__(self, document_id: UUID, version: int) -> None:
        """Store the document id and version, and build a readable message."""
        self.document_id = document_id
        self.version = version
        super().__init__(f"Document {document_id} has no version {version}")
