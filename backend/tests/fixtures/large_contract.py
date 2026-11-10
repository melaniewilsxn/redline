LARGE_DOCUMENT_CHARACTER_COUNT = 10 * 1024 * 1024
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
