import psycopg

from scripts.seed import CONTRACTS_DIRECTORY, seed_documents


def test_seed_skips_when_documents_already_exist(test_database_url: str) -> None:
    """Seeding an empty database loads the contracts, and a second seed adds none."""
    clear_documents(test_database_url)
    contract_count = len(list(CONTRACTS_DIRECTORY.glob("*.txt")))

    try:
        first_count = seed_documents(test_database_url)
        second_count = seed_documents(test_database_url)
        with psycopg.connect(test_database_url) as connection:
            row = connection.execute("SELECT count(*) FROM documents").fetchone()

        assert first_count == contract_count
        assert second_count == 0
        assert row is not None
        assert row[0] == contract_count
    finally:
        clear_documents(test_database_url)


def clear_documents(database_url: str) -> None:
    """Remove documents the seed test committed."""
    with psycopg.connect(database_url, autocommit=True) as connection:
        connection.execute("DELETE FROM documents")
