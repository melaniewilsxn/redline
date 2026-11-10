import logging
import re
import sys
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass

from redline.editing.apply import apply_changes
from redline.editing.models import AppliedEdit, Change, RangeTarget
from redline.search.index import (
    SearchIndex,
    create_search_index,
    index_document,
    update_indexed_document,
)
from redline.search.models import AllDocuments, SearchQuery
from redline.search.query_parser import parse_query
from redline.search.query_runner import run_query
from tests.fixtures.large_contract import (
    LARGE_DOCUMENT_CHARACTER_COUNT,
    build_large_contract,
    build_spread_changes,
    section_number_at,
)

logger = logging.getLogger(__name__)

BENCHMARK_REPEATS = 5
LATE_SECTION_FRACTION = 0.9
PAGE_LIMIT = 20
PAGE_OFFSET = 0
CROSS_DOCUMENT_COUNT = 20
CROSS_DOCUMENT_CHARACTERS = 500 * 1024
ESCROW_DOCUMENT_NUMBER = 7
ESCROW_SENTENCE = "The Escrow Agent shall release the Holdback Amount."
SPREAD_EDIT_COUNT = 100
SINGLE_EDIT_LENGTH = 8
SINGLE_EDIT_REPLACEMENT = "EDITED-TEXT"
TITLE = "Benchmark"
CURRENT_VERSION = 1
NEXT_VERSION = 2
MILLISECONDS_PER_SECOND = 1000
MISSING_BASELINE = "-"


@dataclass(frozen=True)
class BenchmarkRow:
    """One timed case."""

    case: str
    indexed_milliseconds: float
    naive_milliseconds: float | None


def main() -> None:
    """Time the index against plain scans and print the table."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        rows = run_benchmark()
        print_table(rows)
    except Exception:
        logger.exception("Benchmark failed")
        sys.exit(1)


def run_benchmark() -> list[BenchmarkRow]:
    """Build every case and return the median timings."""
    contract = build_large_contract(LARGE_DOCUMENT_CHARACTER_COUNT)
    document_id = uuid.uuid4()
    indexed = create_search_index()
    index_document(indexed, document_id, TITLE, CURRENT_VERSION, contract)
    section_number = section_number_at(contract, LATE_SECTION_FRACTION)
    rare_phrase = f"Schedule {section_number} to the Customer"
    one_edit = apply_changes(
        contract,
        [
            Change(
                target=RangeTarget(
                    start=len(contract) // 2,
                    end=len(contract) // 2 + SINGLE_EDIT_LENGTH,
                ),
                replacement=SINGLE_EDIT_REPLACEMENT,
            )
        ],
    )
    spread_changes = build_spread_changes(len(contract))
    spread = apply_changes(contract, spread_changes[:SPREAD_EDIT_COUNT])
    supplier_pattern = re.compile(r"\bsupplier\b", re.IGNORECASE)
    rejected_pattern = re.compile(r"\brejected\b", re.IGNORECASE)
    return [
        BenchmarkRow("Build 10MB index", measure_index(document_id, contract), None),
        query_row(
            indexed,
            contract,
            f'Rare phrase "{rare_phrase}"',
            f'"{rare_phrase}"',
            re.compile(re.escape(rare_phrase), re.IGNORECASE),
        ),
        query_row(
            indexed,
            contract,
            "Common word customer",
            "customer",
            re.compile(r"\bcustomer\b", re.IGNORECASE),
        ),
        query_row(
            indexed,
            contract,
            'Common phrase "written notice"',
            '"written notice"',
            re.compile(re.escape("written notice"), re.IGNORECASE),
        ),
        BenchmarkRow(
            "Two words supplier rejected",
            measure_query(indexed, parse_query("supplier rejected")),
            measure(lambda: scan_both(supplier_pattern, rejected_pattern, contract)),
        ),
        BenchmarkRow(
            "Update after 1 edit",
            measure_update(document_id, contract, one_edit.text, one_edit.applied_edits),
            measure_index(document_id, one_edit.text),
        ),
        BenchmarkRow(
            "Update after 100 spread edits",
            measure_update(document_id, contract, spread.text, spread.applied_edits),
            measure_index(document_id, spread.text),
        ),
        BenchmarkRow(
            "Apply 1,000 range changes",
            measure(lambda: apply_changes(contract, spread_changes)),
            None,
        ),
        cross_document_row(),
    ]


def query_row(
    index: SearchIndex,
    text: str,
    case: str,
    query_text: str,
    pattern: re.Pattern[str],
) -> BenchmarkRow:
    """Time one query against a case-insensitive scan of the same text."""
    query = parse_query(query_text)
    return BenchmarkRow(
        case,
        measure_query(index, query),
        measure(lambda: count_matches(pattern, text)),
    )


def cross_document_row() -> BenchmarkRow:
    """Time a phrase that occurs in one of twenty documents."""
    base = build_large_contract(CROSS_DOCUMENT_CHARACTERS)
    texts = [
        base + ESCROW_SENTENCE if number == ESCROW_DOCUMENT_NUMBER else base
        for number in range(1, CROSS_DOCUMENT_COUNT + 1)
    ]
    index = create_search_index()
    for number, text in enumerate(texts, start=1):
        index_document(index, uuid.UUID(int=number), f"Contract {number}", CURRENT_VERSION, text)
    query = parse_query('"escrow agent" holdback')
    phrase = re.compile(re.escape("escrow agent"), re.IGNORECASE)
    word = re.compile(r"\bholdback\b", re.IGNORECASE)
    return BenchmarkRow(
        "Cross-document escrow phrase",
        measure_query(index, query),
        measure(lambda: scan_documents(texts, phrase, word)),
    )


def measure_index(document_id: uuid.UUID, text: str) -> float:
    """Return the median time to index text from scratch."""
    samples: list[float] = []
    for _repeat in range(BENCHMARK_REPEATS):
        index = create_search_index()
        started = time.perf_counter()
        index_document(index, document_id, TITLE, CURRENT_VERSION, text)
        samples.append((time.perf_counter() - started) * MILLISECONDS_PER_SECOND)
    return median(samples)


def measure_update(
    document_id: uuid.UUID, original: str, text: str, applied_edits: list[AppliedEdit]
) -> float:
    """Return the median time of the incremental update, after the original is already indexed."""
    samples: list[float] = []
    for _repeat in range(BENCHMARK_REPEATS):
        index = create_search_index()
        index_document(index, document_id, TITLE, CURRENT_VERSION, original)
        started = time.perf_counter()
        update_indexed_document(index, document_id, NEXT_VERSION, text, applied_edits)
        samples.append((time.perf_counter() - started) * MILLISECONDS_PER_SECOND)
    return median(samples)


def measure_query(index: SearchIndex, query: SearchQuery) -> float:
    """Return the median time of one query against an index that is already built."""
    return measure(lambda: run_query(index, query, AllDocuments(), PAGE_LIMIT, PAGE_OFFSET))


def measure(operation: Callable[[], object]) -> float:
    """Return the median duration of operation, in milliseconds."""
    samples: list[float] = []
    for _repeat in range(BENCHMARK_REPEATS):
        started = time.perf_counter()
        operation()
        samples.append((time.perf_counter() - started) * MILLISECONDS_PER_SECOND)
    return median(samples)


def median(samples: list[float]) -> float:
    """Return the middle value of an odd-length sample list."""
    return sorted(samples)[len(samples) // 2]


def count_matches(pattern: re.Pattern[str], text: str) -> int:
    """Count matches of a compiled pattern."""
    return sum(1 for _match in pattern.finditer(text))


def scan_both(supplier: re.Pattern[str], rejected: re.Pattern[str], text: str) -> int:
    """Count matches of both words with two scans."""
    return count_matches(supplier, text) + count_matches(rejected, text)


def scan_documents(texts: list[str], phrase: re.Pattern[str], word: re.Pattern[str]) -> int:
    """Count the phrase and the word across every document."""
    total = 0
    for text in texts:
        total += count_matches(phrase, text)
        total += count_matches(word, text)
    return total


def format_milliseconds(value: float) -> str:
    """Return the millisecond text, with extra digits under one millisecond."""
    if value >= 100:
        return f"{value:.0f}"
    if value >= 1:
        return f"{value:.1f}"
    return f"{value:.3f}"


def print_table(rows: list[BenchmarkRow]) -> None:
    """Print the timings as a Markdown table."""
    print("| Case | Indexed ms | Naive ms | Speedup |")
    print("| --- | ---: | ---: | ---: |")
    for row in rows:
        if row.naive_milliseconds is None:
            naive = MISSING_BASELINE
            speedup = MISSING_BASELINE
        elif row.indexed_milliseconds == 0:
            naive = format_milliseconds(row.naive_milliseconds)
            speedup = MISSING_BASELINE
        else:
            naive = format_milliseconds(row.naive_milliseconds)
            speedup = f"{row.naive_milliseconds / row.indexed_milliseconds:.1f}x"
        print(
            f"| {row.case} | {format_milliseconds(row.indexed_milliseconds)} "
            f"| {naive} | {speedup} |"
        )


if __name__ == "__main__":
    main()
