import logging
from pathlib import Path

from psycopg import Connection
from psycopg_pool import ConnectionPool

logger = logging.getLogger(__name__)

SCHEMA_PATH = Path(__file__).parent / "schema.sql"
POOL_MINIMUM_SIZE = 1
POOL_MAXIMUM_SIZE = 10
DATABASE_READY_STATEMENT = "SELECT 1"


def open_connection_pool(database_url: str) -> ConnectionPool:
    """Open a pool of autocommit connections and wait until it is ready."""
    logger.info("Opening the database connection pool")
    try:
        pool = ConnectionPool(
            conninfo=database_url,
            min_size=POOL_MINIMUM_SIZE,
            max_size=POOL_MAXIMUM_SIZE,
            kwargs={"autocommit": True},
            open=True,
        )
        pool.wait()
    except Exception as error:
        logger.error(f"Failed to open the database connection pool: {get_safe_error_detail(error)}")
        raise
    logger.info("Opened the database connection pool")
    return pool


def apply_schema(connection: Connection) -> None:
    """Create tables and indexes, skipping the ones that already exist."""
    connection.execute(SCHEMA_PATH.read_text())


def check_database(connection: Connection) -> None:
    """Fail when the database does not accept a statement."""
    connection.execute(DATABASE_READY_STATEMENT)


def get_safe_error_detail(error: Exception) -> str:
    """Return an error detail that cannot include a connection string."""
    detail = str(error)
    if "://" in detail or "password" in detail.lower():
        return type(error).__name__
    return detail
