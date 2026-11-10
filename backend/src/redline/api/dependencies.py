from collections.abc import Iterator
from uuid import UUID

from fastapi import Request
from psycopg import Connection

from redline.ai.model_client import RedlineModelClient
from redline.ai.models import Playbook
from redline.services.ai_redline_service import DocumentReader
from redline.services.search_service import SearchService
from redline.storage.document_repository import get_document
from redline.storage.models import StoredDocument


def get_connection(request: Request) -> Iterator[Connection]:
    """Yield one pooled connection for this request."""
    with request.app.state.connection_pool.connection() as connection:
        yield connection


def get_search_service(request: Request) -> SearchService:
    """Return the search index for this process."""
    return request.app.state.search_service


def get_model_client(request: Request) -> RedlineModelClient:
    """Return the model client for this process."""
    return request.app.state.model_client


def get_playbook(request: Request) -> Playbook:
    """Return the playbook loaded at startup."""
    return request.app.state.playbook


def get_document_reader(request: Request) -> DocumentReader:
    """Return a reader that borrows a connection only while it loads the document."""

    def read_document(document_id: UUID) -> StoredDocument:
        """Load one document and release the connection before returning."""
        with request.app.state.connection_pool.connection() as connection:
            return get_document(connection, document_id)

    return read_document
