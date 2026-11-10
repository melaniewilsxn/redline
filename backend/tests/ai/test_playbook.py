import json
from pathlib import Path

import pytest

from redline.ai.playbook import PLAYBOOK_PATH, load_playbook

POSITION_TOPICS = (
    "Indemnification",
    "Limitation of liability",
    "Governing law",
    "Termination for convenience",
    "Assignment",
    "Confidentiality term",
)


def test_sample_playbook_loads_every_position() -> None:
    """The sample playbook is for the Customer and has the six positions."""
    playbook = load_playbook(PLAYBOOK_PATH)

    assert playbook.represented_party == "Customer"
    assert [position.topic for position in playbook.positions] == list(POSITION_TOPICS)


def test_position_missing_field_raises_value_error(tmp_path: Path) -> None:
    """A position without a required field fails to load."""
    path = tmp_path / "playbook.json"
    path.write_text(
        json.dumps(
            {
                "represented_party": "Customer",
                "positions": [{"topic": "Indemnification"}],
            }
        )
    )

    with pytest.raises(ValueError):
        load_playbook(path)
