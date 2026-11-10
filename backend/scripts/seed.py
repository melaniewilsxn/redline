import argparse
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

from psycopg import Connection

from redline.config import load_settings
from redline.logging_setup import configure_logging
from redline.services.document_service import create_document
from redline.services.search_service import SearchService
from redline.storage.database import apply_schema, get_safe_error_detail, open_connection_pool
from redline.storage.document_repository import list_documents

logger = logging.getLogger(__name__)

CONTRACTS_DIRECTORY = Path(__file__).resolve().parents[2] / "sample_data" / "contracts"
SEED_AUTHOR = "Seed"
EXISTING_DOCUMENT_PROBE_LIMIT = 1
EXISTING_DOCUMENT_PROBE_OFFSET = 0


@dataclass(frozen=True)
class SeedArguments:
    """Whether this run deletes the documents already stored."""

    reset: bool


def main() -> None:
    """Load the sample contracts, or replace every document when reset is set."""
    arguments = parse_arguments()
    try:
        settings = load_settings()
        configure_logging(settings.log_level)
        if arguments.reset:
            seeded_count = reseed_documents(settings.database_url)
        else:
            seeded_count = seed_documents(settings.database_url)
        logger.info(f"Finished seeding {seeded_count} documents")
    except Exception as error:
        logger.error(f"Failed to seed documents: {get_safe_error_detail(error)}")
        sys.exit(1)


def parse_arguments() -> SeedArguments:
    """Read whether this run should delete the existing documents first."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true")
    parsed = parser.parse_args()
    return SeedArguments(reset=parsed.reset)


def seed_documents(database_url: str) -> int:
    """Create one document per contract file when the database is empty."""
    contract_paths = list_contract_paths()
    pool = open_connection_pool(database_url)
    try:
        with pool.connection() as connection:
            apply_schema(connection)
            existing = list_documents(
                connection,
                EXISTING_DOCUMENT_PROBE_LIMIT,
                EXISTING_DOCUMENT_PROBE_OFFSET,
            )
            if existing.total_count > 0:
                logger.info(f"Skipping seed because {existing.total_count} documents already exist")
                return 0
            return load_contracts(connection, contract_paths)
    finally:
        pool.close()


def reseed_documents(database_url: str) -> int:
    """Delete every document, then load the sample contracts."""
    contract_paths = list_contract_paths()
    pool = open_connection_pool(database_url)
    try:
        with pool.connection() as connection:
            apply_schema(connection)
            with connection.transaction():
                existing = list_documents(
                    connection,
                    EXISTING_DOCUMENT_PROBE_LIMIT,
                    EXISTING_DOCUMENT_PROBE_OFFSET,
                )
                connection.execute("TRUNCATE documents CASCADE")
                logger.info(f"Removed {existing.total_count} documents before seeding")
                return load_contracts(connection, contract_paths)
    finally:
        pool.close()


def list_contract_paths() -> list[Path]:
    """Return the sample contract files."""
    contract_paths = sorted(CONTRACTS_DIRECTORY.glob("*.txt"))
    if not contract_paths:
        raise RuntimeError(f"No contracts found in {CONTRACTS_DIRECTORY}")
    return contract_paths


def load_contracts(connection: Connection, contract_paths: list[Path]) -> int:
    """Create one document for each sample contract."""
    search_service = SearchService()
    for path in contract_paths:
        title = path.stem.replace("_", " ")
        create_document(connection, title, path.read_text(), SEED_AUTHOR, search_service)
    return len(contract_paths)


if __name__ == "__main__":
    main()
