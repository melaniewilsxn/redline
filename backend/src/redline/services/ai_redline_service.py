import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from redline.ai.anchoring import anchor_suggestions
from redline.ai.model_client import RedlineModelClient
from redline.ai.models import AnchoredSuggestions, Playbook
from redline.ai.playbook import format_playbook
from redline.ai.prompts import EXCERPT_SEPARATOR, SYSTEM_PROMPT, build_user_prompt
from redline.services.search_service import SearchService
from redline.storage.models import StoredDocument

logger = logging.getLogger(__name__)

FULL_DOCUMENT_CHARACTER_LIMIT = 100_000
RETRIEVED_CHUNK_LIMIT = 12

DocumentReader = Callable[[UUID], StoredDocument]


class ContractTextSource(StrEnum):
    """Whether the model saw the whole document or retrieved excerpts."""

    WHOLE_DOCUMENT = "whole document"
    EXCERPTS = "excerpts"


@dataclass(frozen=True)
class ContractPrompt:
    """The contract text sent to the model, and how it was chosen."""

    text: str
    source: ContractTextSource
    excerpt_count: int


@dataclass(frozen=True)
class DocumentRedlineSuggestions:
    """Suggestions for one document version."""

    document_id: UUID
    version: int
    suggestions: AnchoredSuggestions


def suggest_redlines(
    read_document: DocumentReader,
    search_service: SearchService,
    model_client: RedlineModelClient,
    playbook: Playbook,
    document_id: UUID,
    instruction: str,
) -> DocumentRedlineSuggestions:
    """Ask the model for suggestions and pin them to this document version."""
    document = read_document(document_id)
    logger.info(
        f"Started AI redlines for document {document.id} version {document.version}, "
        f"length {len(document.text)}, instruction length {len(instruction)}"
    )
    started = time.perf_counter()
    contract_prompt = contract_text_for_prompt(document, search_service, instruction)
    suggestions = model_client.request_suggestions(
        SYSTEM_PROMPT,
        build_user_prompt(instruction, format_playbook(playbook), contract_prompt.text),
    )
    anchored = anchor_suggestions(document.text, suggestions)
    elapsed = time.perf_counter() - started
    logger.info(
        f"Finished AI redlines for document {document.id} version {document.version} "
        f"from {contract_prompt.source.value}, {contract_prompt.excerpt_count} excerpts, "
        f"{len(anchored.anchored)} anchored, {len(anchored.dropped)} dropped, "
        f"{elapsed:.3f} seconds"
    )
    return DocumentRedlineSuggestions(
        document_id=document.id,
        version=document.version,
        suggestions=anchored,
    )


def contract_text_for_prompt(
    document: StoredDocument, search_service: SearchService, instruction: str
) -> ContractPrompt:
    """Return the text to send, either the whole document or the relevant excerpts."""
    if len(document.text) <= FULL_DOCUMENT_CHARACTER_LIMIT:
        return ContractPrompt(
            text=document.text, source=ContractTextSource.WHOLE_DOCUMENT, excerpt_count=0
        )
    spans = search_service.find_relevant_spans(document, instruction, RETRIEVED_CHUNK_LIMIT)
    excerpts = [document.text[span.start : span.end] for span in spans]
    return ContractPrompt(
        text=EXCERPT_SEPARATOR.join(excerpts),
        source=ContractTextSource.EXCERPTS,
        excerpt_count=len(spans),
    )
