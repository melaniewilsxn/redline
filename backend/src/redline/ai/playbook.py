import json
import logging
from pathlib import Path

from redline.ai.models import Playbook, PlaybookPosition

logger = logging.getLogger(__name__)

PLAYBOOK_PATH = Path(__file__).resolve().parents[4] / "sample_data" / "playbook.json"
REPRESENTED_PARTY_KEY = "represented_party"
POSITIONS_KEY = "positions"
TOPIC_KEY = "topic"
PREFERRED_POSITION_KEY = "preferred_position"
ACCEPTABLE_FALLBACKS_KEY = "acceptable_fallbacks"
NEVER_ACCEPT_KEY = "never_accept"


def load_playbook(path: Path) -> Playbook:
    """Read a playbook file. A broken file is logged and raised."""
    logger.info(f"Started loading playbook {path.name}")
    try:
        payload = json.loads(path.read_text())
    except OSError as error:
        logger.error(f"Failed to read playbook {path.name}: {type(error).__name__}")
        raise
    except json.JSONDecodeError as error:
        logger.error(f"Playbook {path.name} is not JSON: {type(error).__name__}")
        raise
    playbook = read_playbook(payload)
    logger.info(f"Finished loading playbook {path.name} with {len(playbook.positions)} positions")
    return playbook


def read_playbook(payload: object) -> Playbook:
    """Build a playbook from a decoded JSON object."""
    if not isinstance(payload, dict):
        logger.error("Playbook JSON is not an object")
        raise ValueError(REPRESENTED_PARTY_KEY)
    represented_party = read_string(payload, REPRESENTED_PARTY_KEY)
    if POSITIONS_KEY not in payload or not isinstance(payload[POSITIONS_KEY], list):
        logger.error(f"Playbook is missing {POSITIONS_KEY}")
        raise ValueError(POSITIONS_KEY)
    positions = [read_position(position) for position in payload[POSITIONS_KEY]]
    return Playbook(represented_party=represented_party, positions=positions)


def read_position(payload: object) -> PlaybookPosition:
    """Build one position from a decoded JSON object."""
    if not isinstance(payload, dict):
        logger.error("A playbook position is not an object")
        raise ValueError(TOPIC_KEY)
    return PlaybookPosition(
        topic=read_string(payload, TOPIC_KEY),
        preferred_position=read_string(payload, PREFERRED_POSITION_KEY),
        acceptable_fallbacks=read_string_list(payload, ACCEPTABLE_FALLBACKS_KEY),
        never_accept=read_string_list(payload, NEVER_ACCEPT_KEY),
    )


def read_string(payload: dict[str, object], key: str) -> str:
    """Return a string field, or raise when it is missing or not a string."""
    if key not in payload or not isinstance(payload[key], str):
        logger.error(f"Playbook is missing {key}")
        raise ValueError(key)
    return payload[key]


def read_string_list(payload: dict[str, object], key: str) -> list[str]:
    """Return a list of strings, or raise when it is missing or not that list."""
    if key not in payload or not isinstance(payload[key], list):
        logger.error(f"Playbook is missing {key}")
        raise ValueError(key)
    values = payload[key]
    strings: list[str] = []
    for value in values:
        if not isinstance(value, str):
            logger.error(f"Playbook field {key} contains a non-string")
            raise ValueError(key)
        strings.append(value)
    return strings


def format_playbook(playbook: Playbook) -> str:
    """Render the positions as plain text for the prompt."""
    lines = [f"Represented party: {playbook.represented_party}"]
    for position in playbook.positions:
        fallbacks = "; ".join(position.acceptable_fallbacks)
        never_accept = "; ".join(position.never_accept)
        lines.append(
            f"{position.topic}: prefer {position.preferred_position}. "
            f"Acceptable: {fallbacks}. Never accept: {never_accept}."
        )
    return "\n".join(lines)
