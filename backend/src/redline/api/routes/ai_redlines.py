import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response

from redline.ai.model_client import RedlineModelClient
from redline.ai.models import Playbook
from redline.api.dependencies import (
    get_document_reader,
    get_model_client,
    get_playbook,
    get_search_service,
)
from redline.api.etags import build_etag
from redline.api.schemas import (
    AiRedlineRequest,
    AiRedlineResponse,
    DroppedSuggestionResponse,
    SuggestionResponse,
)
from redline.services.ai_redline_service import (
    DocumentReader,
    DocumentRedlineSuggestions,
    suggest_redlines,
)
from redline.services.search_service import SearchService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/documents/{document_id}/ai-redlines")
def suggest_document_redlines(
    document_id: UUID,
    body: AiRedlineRequest,
    response: Response,
    read_document: Annotated[DocumentReader, Depends(get_document_reader)],
    search_service: Annotated[SearchService, Depends(get_search_service)],
    model_client: Annotated[RedlineModelClient, Depends(get_model_client)],
    playbook: Annotated[Playbook, Depends(get_playbook)],
) -> AiRedlineResponse:
    """Return anchored and dropped suggestions for this document version."""
    logger.info(
        f"Started AI redlines for document {document_id}, "
        f"instruction length {len(body.instruction)}"
    )
    result = suggest_redlines(
        read_document,
        search_service,
        model_client,
        playbook,
        document_id,
        body.instruction,
    )
    response.headers["ETag"] = build_etag(result.document_id, result.version)
    logger.info(
        f"Finished AI redlines for document {result.document_id} version {result.version}, "
        f"{len(result.suggestions.anchored)} anchored, {len(result.suggestions.dropped)} dropped"
    )
    return ai_redline_response(result)


def ai_redline_response(result: DocumentRedlineSuggestions) -> AiRedlineResponse:
    """Map anchored and dropped suggestions onto the response body."""
    return AiRedlineResponse(
        document_id=result.document_id,
        version=result.version,
        suggestions=[
            SuggestionResponse(
                suggestion_id=suggestion.suggestion_id,
                start=suggestion.span.start,
                end=suggestion.span.end,
                original_text=suggestion.original_text,
                replacement=suggestion.replacement,
                rationale=suggestion.rationale,
            )
            for suggestion in result.suggestions.anchored
        ],
        dropped=[
            DroppedSuggestionResponse(
                suggestion_id=suggestion.suggestion_id,
                text=suggestion.text,
                replacement=suggestion.replacement,
                rationale=suggestion.rationale,
                reason=suggestion.reason,
            )
            for suggestion in result.suggestions.dropped
        ],
    )
