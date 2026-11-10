from collections.abc import Iterator

from fastapi import Request
from psycopg import Connection


def get_connection(request: Request) -> Iterator[Connection]:
    """Yield one pooled connection for this request."""
    with request.app.state.connection_pool.connection() as connection:
        yield connection
