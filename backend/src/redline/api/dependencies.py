from collections.abc import Iterator

from fastapi import Request
from psycopg import Connection

from redline.services.search_service import SearchService


def get_connection(request: Request) -> Iterator[Connection]:
    """Yield one pooled connection for this request."""
    with request.app.state.connection_pool.connection() as connection:
        yield connection


def get_search_service(request: Request) -> SearchService:
    """Return the search index for this process."""
    return request.app.state.search_service
