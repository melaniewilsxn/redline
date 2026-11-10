import re
from enum import Enum, auto

from redline.editing.models import Change, RangeTarget

LARGE_DOCUMENT_CHARACTER_COUNT = 10 * 1024 * 1024
CHANGE_COUNT = 1000
REPLACED_CHARACTER_COUNT = 8
LONGER_REPLACEMENT = "LONGER-TEXT"
SHORTER_REPLACEMENT = "x"
DELETION_REPLACEMENT = ""
INSERT_TEXT = "INS"
SECTION_PATTERN = re.compile(r"Section (\d+)\.")
SECTION_TEMPLATE = (
    "Section {number}. Delivery. The Supplier shall deliver the Goods described in "
    "Schedule {number} to the Customer within thirty (30) days of the Order Date. "
    "The Customer may reject non-conforming Goods by written notice.\n\n"
)


def build_large_contract(minimum_character_count: int) -> str:
    """Repeat the delivery clause until the text reaches minimum_character_count."""
    sections: list[str] = []
    character_count = 0
    section_number = 1
    while character_count < minimum_character_count:
        section = SECTION_TEMPLATE.format(number=section_number)
        sections.append(section)
        character_count += len(section)
        section_number += 1
    return "".join(sections)


class EditPattern(Enum):
    """Which replacement a spread change uses."""

    LONGER = auto()
    SHORTER = auto()
    DELETION = auto()
    INSERT = auto()


EDIT_PATTERNS = (
    EditPattern.LONGER,
    EditPattern.SHORTER,
    EditPattern.DELETION,
    EditPattern.INSERT,
)


def build_spread_changes(document_length: int) -> list[Change]:
    """Build non-overlapping range changes spread evenly across the document."""
    stride = document_length // CHANGE_COUNT
    changes: list[Change] = []
    for index in range(CHANGE_COUNT):
        start = index * stride
        match EDIT_PATTERNS[index % len(EDIT_PATTERNS)]:
            case EditPattern.LONGER:
                end = start + REPLACED_CHARACTER_COUNT
                replacement = LONGER_REPLACEMENT
            case EditPattern.SHORTER:
                end = start + REPLACED_CHARACTER_COUNT
                replacement = SHORTER_REPLACEMENT
            case EditPattern.DELETION:
                end = start + REPLACED_CHARACTER_COUNT
                replacement = DELETION_REPLACEMENT
            case EditPattern.INSERT:
                end = start
                replacement = INSERT_TEXT
            case _:
                raise RuntimeError(f"Unknown edit pattern for change {index}")
        changes.append(Change(target=RangeTarget(start=start, end=end), replacement=replacement))
    return changes


def section_number_at(text: str, fraction: float) -> int:
    """Return the section number at this fraction of the text."""
    position = int(len(text) * fraction)
    earlier = text.rfind("Section ", 0, position)
    if earlier < 0:
        earlier = 0
    match = SECTION_PATTERN.search(text, earlier)
    if match is None:
        raise RuntimeError(f"No section number near position {position}")
    return int(match.group(1))
