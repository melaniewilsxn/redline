import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from redline.api.dependencies import get_search_service
from redline.api.schemas import (
    DEFAULT_PAGE_LIMIT,
    MAXIMUM_PAGE_LIMIT,
    MINIMUM_PAGE_LIMIT,
    MINIMUM_PAGE_OFFSET,
    SearchHitResponse,
    SearchResponse,
    SnippetResponse,
    TextSpanResponse,
)
from redline.search.models import (
    AllDocuments,
    SearchMatchMode,
    SearchPage,
    SearchScope,
    SelectedDocuments,
)
from redline.search.query_parser import MAXIMUM_QUERY_CHARACTERS
from redline.services.search_service import SearchService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/search")
def search_documents(
    search_service: Annotated[SearchService, Depends(get_search_service)],
    q: Annotated[str, Query(min_length=1, max_length=MAXIMUM_QUERY_CHARACTERS)],
    document_ids: Annotated[list[UUID], Query(default_factory=list)],
    limit: Annotated[int, Query(ge=MINIMUM_PAGE_LIMIT, le=MAXIMUM_PAGE_LIMIT)] = DEFAULT_PAGE_LIMIT,
    offset: Annotated[int, Query(ge=MINIMUM_PAGE_OFFSET)] = MINIMUM_PAGE_OFFSET,
    mode: Annotated[SearchMatchMode, Query()] = SearchMatchMode.EXACT,
) -> SearchResponse:
    """Search every document, or only the ids that were given."""
    if document_ids:
        scope: SearchScope = SelectedDocuments(document_ids=document_ids)
        logger.info(
            f"Started searching {len(document_ids)} selected documents "
            f"with limit {limit} offset {offset}"
        )
    else:
        scope = AllDocuments()
        logger.info(f"Started searching all documents with limit {limit} offset {offset}")
    page = search_service.search(q, scope, limit, offset, mode)
    logger.info(f"Finished searching with {page.total_count} hits, limit {limit} offset {offset}")
    return build_search_response(page, limit, offset)


@router.get("/documents/{document_id}/search")
def search_document(
    document_id: UUID,
    search_service: Annotated[SearchService, Depends(get_search_service)],
    q: Annotated[str, Query(min_length=1, max_length=MAXIMUM_QUERY_CHARACTERS)],
    limit: Annotated[int, Query(ge=MINIMUM_PAGE_LIMIT, le=MAXIMUM_PAGE_LIMIT)] = DEFAULT_PAGE_LIMIT,
    offset: Annotated[int, Query(ge=MINIMUM_PAGE_OFFSET)] = MINIMUM_PAGE_OFFSET,
    mode: Annotated[SearchMatchMode, Query()] = SearchMatchMode.EXACT,
) -> SearchResponse:
    """Search one document. A document that is not indexed is a 404."""
    logger.info(f"Started searching document {document_id} with limit {limit} offset {offset}")
    page = search_service.search(
        q, SelectedDocuments(document_ids=[document_id]), limit, offset, mode
    )
    logger.info(
        f"Finished searching document {document_id} with {page.total_count} hits, "
        f"limit {limit} offset {offset}"
    )
    return build_search_response(page, limit, offset)


def build_search_response(page: SearchPage, limit: int, offset: int) -> SearchResponse:
    """Map a page of hits onto the response body."""
    return SearchResponse(
        hits=[
            SearchHitResponse(
                document_id=hit.document_id,
                title=hit.title,
                version=hit.version,
                score=hit.score,
                match_count=hit.match_count,
                snippets=[
                    SnippetResponse(
                        start=snippet.span.start,
                        end=snippet.span.end,
                        text=snippet.text,
                        highlights=[
                            TextSpanResponse(start=highlight.start, end=highlight.end)
                            for highlight in snippet.highlights
                        ],
                    )
                    for snippet in hit.snippets
                ],
            )
            for hit in page.hits
        ],
        total_count=page.total_count,
        limit=limit,
        offset=offset,
    )
