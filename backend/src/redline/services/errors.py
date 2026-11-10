from uuid import UUID


class ServiceError(Exception):
    """Base class for service failures."""


class StaleVersionError(ServiceError):
    """The caller's version is no longer the document's current version."""

    def __init__(self, document_id: UUID, expected_version: int, current_version: int) -> None:
        """Store both versions and build a readable message."""
        self.document_id = document_id
        self.expected_version = expected_version
        self.current_version = current_version
        super().__init__(
            f"Document {document_id} is at version {current_version}, not {expected_version}"
        )
