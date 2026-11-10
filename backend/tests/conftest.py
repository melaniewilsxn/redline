import os
from collections.abc import Iterator
from uuid import UUID

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg import Connection

from redline.api.dependencies import get_connection, get_document_reader
from redline.config import Settings
from redline.main import create_app
from redline.services.ai_redline_service import DocumentReader
from redline.storage.database import apply_schema
from redline.storage.document_repository import get_document
from redline.storage.models import StoredDocument

TEST_DATABASE_URL_VARIABLE = "TEST_DATABASE_URL"
TEST_LOG_LEVEL = "WARNING"


@pytest.fixture(scope="session")
def test_database_url() -> str:
    """Return the test database URL, or fail when it is missing."""
    if TEST_DATABASE_URL_VARIABLE not in os.environ:
        raise RuntimeError(f"Environment variable {TEST_DATABASE_URL_VARIABLE} is missing")
    return os.environ[TEST_DATABASE_URL_VARIABLE]


@pytest.fixture(scope="session")
def test_settings(test_database_url: str) -> Settings:
    """Settings that point the app at the test database."""
    return Settings(
        database_url=test_database_url,
        log_level=TEST_LOG_LEVEL,
        anthropic_api_key=None,
    )


@pytest.fixture(scope="session")
def schema_ready(test_database_url: str) -> None:
    """Create the tables once for the test session."""
    with psycopg.connect(test_database_url, autocommit=True) as connection:
        apply_schema(connection)


@pytest.fixture
def connection(schema_ready: None, test_database_url: str) -> Iterator[Connection]:
    """Yield a connection whose writes roll back at the end of the test."""
    with (
        psycopg.connect(test_database_url, autocommit=True) as test_connection,
        test_connection.transaction(force_rollback=True),
    ):
        yield test_connection


@pytest.fixture
def client(connection: Connection, test_settings: Settings) -> Iterator[TestClient]:
    """Yield a client whose routes use the rolled-back connection."""

    def yield_test_connection() -> Iterator[Connection]:
        """Yield the rolled-back test connection."""
        yield connection

    def read_test_document(document_id: UUID) -> StoredDocument:
        """Read through the rolled-back test connection."""
        return get_document(connection, document_id)

    def override_document_reader() -> DocumentReader:
        """Return the rolled-back document reader."""
        return read_test_document

    app = create_app(test_settings)
    app.dependency_overrides[get_connection] = yield_test_connection
    app.dependency_overrides[get_document_reader] = override_document_reader
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
