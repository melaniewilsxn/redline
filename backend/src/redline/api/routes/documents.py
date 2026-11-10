import logging
from http import HTTPStatus
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Response
from psycopg import Connection

from redline.api.dependencies import get_connection
from redline.api.etags import PreconditionRequiredError, build_etag, parse_if_match
from redline.api.schemas import (
    AppliedEditResponse,
    ApplyChangesRequest,
    ApplyChangesResponse,
    CreateDocumentRequest,
    DocumentListResponse,
    DocumentResponse,
    DocumentSummaryResponse,
    DocumentVersionResponse,
    VersionSummaryResponse,
    to_change,
)
from redline.services import document_service
from redline.storage import document_repository

logger = logging.getLogger(__name__)

router = APIRouter()

MINIMUM_PAGE_LIMIT = 1
MAXIMUM_PAGE_LIMIT = 100
DEFAULT_PAGE_LIMIT = 20
MINIMUM_PAGE_OFFSET = 0
DOCUMENT_LOCATION = "/documents/{document_id}"


@router.post("/documents", status_code=HTTPStatus.CREATED)
def create_document(
    body: CreateDocumentRequest,
    response: Response,
    connection: Annotated[Connection, Depends(get_connection)],
) -> DocumentResponse:
    """Store a new document and return it."""
    logger.info(f"Started creating a document of {len(body.text)} characters")
    document = document_service.create_document(connection, body.title, body.text, body.author)
    response.headers["ETag"] = build_etag(document.id, document.version)
    response.headers["Location"] = DOCUMENT_LOCATION.format(document_id=document.id)
    logger.info(f"Finished creating document {document.id} at version {document.version}")
    return DocumentResponse(
        id=document.id,
        title=document.title,
        version=document.version,
        text=document.text,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


@router.get("/documents")
def list_documents(
    connection: Annotated[Connection, Depends(get_connection)],
    limit: Annotated[int, Query(ge=MINIMUM_PAGE_LIMIT, le=MAXIMUM_PAGE_LIMIT)] = DEFAULT_PAGE_LIMIT,
    offset: Annotated[int, Query(ge=MINIMUM_PAGE_OFFSET)] = MINIMUM_PAGE_OFFSET,
) -> DocumentListResponse:
    """Return one page of documents, without their text."""
    logger.info(f"Started listing documents at limit {limit} offset {offset}")
    page = document_repository.list_documents(connection, limit, offset)
    logger.info(f"Finished listing {len(page.documents)} of {page.total_count} documents")
    return DocumentListResponse(
        documents=[
            DocumentSummaryResponse(
                id=summary.id,
                title=summary.title,
                version=summary.version,
                character_count=summary.character_count,
                updated_at=summary.updated_at,
            )
            for summary in page.documents
        ],
        total_count=page.total_count,
        limit=limit,
        offset=offset,
    )


@router.get("/documents/{document_id}")
def read_document(
    document_id: UUID,
    response: Response,
    connection: Annotated[Connection, Depends(get_connection)],
) -> DocumentResponse:
    """Return one document and its current text."""
    logger.info(f"Started reading document {document_id}")
    document = document_repository.get_document(connection, document_id)
    response.headers["ETag"] = build_etag(document.id, document.version)
    logger.info(f"Finished reading document {document_id} at version {document.version}")
    return DocumentResponse(
        id=document.id,
        title=document.title,
        version=document.version,
        text=document.text,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


@router.patch("/documents/{document_id}")
def apply_changes(
    document_id: UUID,
    body: ApplyChangesRequest,
    response: Response,
    connection: Annotated[Connection, Depends(get_connection)],
    if_match: Annotated[str | None, Header()] = None,
) -> ApplyChangesResponse:
    """Apply a batch of changes when If-Match names the current version."""
    logger.info(f"Started applying {len(body.changes)} changes to document {document_id}")
    if if_match is None:
        raise PreconditionRequiredError()
    expected_version = parse_if_match(if_match, document_id)
    changes = [
        to_change(change_request, change_index)
        for change_index, change_request in enumerate(body.changes)
    ]
    applied = document_service.apply_document_changes(
        connection,
        document_id,
        expected_version,
        changes,
        body.author,
    )
    response.headers["ETag"] = build_etag(applied.document.id, applied.document.version)
    logger.info(
        f"Finished applying changes to document {document_id} at version {applied.document.version}"
    )
    document = applied.document
    return ApplyChangesResponse(
        document=DocumentResponse(
            id=document.id,
            title=document.title,
            version=document.version,
            text=document.text,
            created_at=document.created_at,
            updated_at=document.updated_at,
        ),
        applied_edits=[
            AppliedEditResponse(
                start=edit.span.start,
                end=edit.span.end,
                replacement_length=edit.replacement_length,
            )
            for edit in applied.applied_edits
        ],
    )


@router.get("/documents/{document_id}/versions")
def list_versions(
    document_id: UUID,
    connection: Annotated[Connection, Depends(get_connection)],
) -> list[VersionSummaryResponse]:
    """Return every saved version of a document, newest first."""
    logger.info(f"Started listing versions of document {document_id}")
    versions = document_repository.list_document_versions(connection, document_id)
    logger.info(f"Finished listing {len(versions)} versions of document {document_id}")
    return [
        VersionSummaryResponse(
            version=version_summary.version,
            author=version_summary.author,
            summary=version_summary.summary,
            character_count=version_summary.character_count,
            created_at=version_summary.created_at,
        )
        for version_summary in versions
    ]


@router.get("/documents/{document_id}/versions/{version}")
def read_version(
    document_id: UUID,
    version: int,
    connection: Annotated[Connection, Depends(get_connection)],
) -> DocumentVersionResponse:
    """Return one saved version, including its text."""
    logger.info(f"Started reading document {document_id} version {version}")
    document_version = document_repository.get_document_version(connection, document_id, version)
    logger.info(f"Finished reading document {document_id} version {version}")
    return DocumentVersionResponse(
        document_id=document_version.document_id,
        version=document_version.version,
        text=document_version.text,
        author=document_version.author,
        summary=document_version.summary,
        created_at=document_version.created_at,
    )
