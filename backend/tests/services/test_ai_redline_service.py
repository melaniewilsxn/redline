from datetime import UTC, datetime
from uuid import UUID

import pytest

from redline.ai.models import Playbook, PlaybookPosition, RedlineSuggestion
from redline.services.ai_redline_service import DocumentReader, suggest_redlines
from redline.services.search_service import SearchService
from redline.storage.errors import DocumentNotFoundError
from redline.storage.models import StoredDocument
from tests.fixtures.fake_model_client import FakeModelClient

DOCUMENT_ID = UUID("00000000-0000-7000-8000-000000000070")
TITLE = "Notes"
VERSION = 1
AUTHOR_TIME = datetime(2026, 1, 1, tzinfo=UTC)
INSTRUCTION = "Review the indemnity"
PLAYBOOK = Playbook(
    represented_party="Customer",
    positions=[
        PlaybookPosition(
            topic="Indemnification",
            preferred_position="mutual",
            acceptable_fallbacks=["capped"],
            never_accept=["one-way from the Customer"],
        )
    ],
)


def test_short_document_is_sent_whole() -> None:
    """A short document is sent in full."""
    text = "The indemnity is one way."
    model = FakeModelClient(suggestions=[])

    suggest_redlines(
        build_document_reader(text),
        SearchService(),
        model,
        PLAYBOOK,
        DOCUMENT_ID,
        INSTRUCTION,
    )

    assert text in model.user_prompt
    assert "<contract>" in model.user_prompt


def test_long_document_sends_only_retrieved_excerpts(monkeypatch: pytest.MonkeyPatch) -> None:
    """A long document sends the matching paragraph and leaves the other one out."""
    text = "The indemnity is one way.\n\nThe weather is fine today.\n\n"
    monkeypatch.setattr(
        "redline.services.ai_redline_service.FULL_DOCUMENT_CHARACTER_LIMIT",
        len(text) - 1,
    )
    model = FakeModelClient(suggestions=[])

    suggest_redlines(
        build_document_reader(text),
        SearchService(),
        model,
        PLAYBOOK,
        DOCUMENT_ID,
        INSTRUCTION,
    )

    assert "The indemnity is one way." in model.user_prompt
    assert "The weather is fine today." not in model.user_prompt


def test_suggestions_anchor_against_the_full_text_when_excerpts_are_sent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A quote from a paragraph the model did not see still anchors in the full text."""
    text = "The indemnity is one way.\n\nThe escrow clause is special.\n\n"
    monkeypatch.setattr(
        "redline.services.ai_redline_service.FULL_DOCUMENT_CHARACTER_LIMIT",
        len(text) - 1,
    )
    model = FakeModelClient(
        suggestions=[
            RedlineSuggestion(
                text="The escrow clause is special.",
                prefix="",
                suffix="",
                replacement="The escrow clause is mutual.",
                rationale="Balance the escrow.",
            )
        ]
    )

    result = suggest_redlines(
        build_document_reader(text), SearchService(), model, PLAYBOOK, DOCUMENT_ID, INSTRUCTION
    )

    assert "The escrow clause is special." not in model.user_prompt
    assert len(result.suggestions.anchored) == 1
    assert result.suggestions.anchored[0].original_text == "The escrow clause is special."
    assert result.suggestions.dropped == []


def test_missing_document_raises_document_not_found_error() -> None:
    """A missing document is not sent to the model."""

    def read_document(document_id: UUID) -> StoredDocument:
        """Raise the missing-document error."""
        raise DocumentNotFoundError(document_id)

    with pytest.raises(DocumentNotFoundError):
        suggest_redlines(
            read_document,
            SearchService(),
            FakeModelClient(suggestions=[]),
            PLAYBOOK,
            DOCUMENT_ID,
            INSTRUCTION,
        )


def build_document_reader(text: str) -> DocumentReader:
    """Return a reader for one stored document."""

    def read_document(document_id: UUID) -> StoredDocument:
        """Return the stored document."""
        return StoredDocument(
            id=document_id,
            title=TITLE,
            version=VERSION,
            text=text,
            created_at=AUTHOR_TIME,
            updated_at=AUTHOR_TIME,
        )

    return read_document
