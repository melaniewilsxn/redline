import logging
from collections.abc import Callable
from dataclasses import asdict, dataclass
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse

from redline.api.etags import PreconditionFailedError, PreconditionRequiredError
from redline.api.schemas import (
    ErrorResponse,
    ErrorType,
)
from redline.editing.errors import (
    AmbiguousTargetError,
    InvalidTargetError,
    OverlappingChangesError,
    RangeOutOfBoundsError,
    TargetNotFoundError,
)
from redline.logging_setup import REQUEST_ID_HEADER, request_id_context
from redline.search.errors import DocumentNotIndexedError, EmptyQueryError
from redline.services.errors import StaleVersionError
from redline.storage.errors import DocumentNotFoundError, DocumentVersionNotFoundError

logger = logging.getLogger(__name__)

INTERNAL_ERROR_MESSAGE = "Internal server error"
VALIDATION_LOCATION = "request"
VALIDATION_ERROR_KIND = "validation_error"
INVALID_REQUEST_SUMMARY = "Request is invalid"
UNKNOWN_STATUS_PHRASE = "Error"


@dataclass(frozen=True)
class ValidationSummary:
    """The location, kind, and client text of the first validation failure."""

    location: str
    error_kind: str
    summary: str


@dataclass(frozen=True)
class KnownError:
    """How one failure class maps onto an error response."""

    exception_class: type[Exception]
    status: HTTPStatus
    error_type: ErrorType


KNOWN_ERRORS = (
    KnownError(InvalidTargetError, HTTPStatus.UNPROCESSABLE_CONTENT, ErrorType.INVALID_TARGET),
    KnownError(
        RangeOutOfBoundsError, HTTPStatus.UNPROCESSABLE_CONTENT, ErrorType.RANGE_OUT_OF_BOUNDS
    ),
    KnownError(TargetNotFoundError, HTTPStatus.UNPROCESSABLE_CONTENT, ErrorType.TARGET_NOT_FOUND),
    KnownError(AmbiguousTargetError, HTTPStatus.UNPROCESSABLE_CONTENT, ErrorType.AMBIGUOUS_TARGET),
    KnownError(
        OverlappingChangesError, HTTPStatus.UNPROCESSABLE_CONTENT, ErrorType.OVERLAPPING_CHANGES
    ),
    KnownError(EmptyQueryError, HTTPStatus.UNPROCESSABLE_CONTENT, ErrorType.INVALID_QUERY),
    KnownError(DocumentNotFoundError, HTTPStatus.NOT_FOUND, ErrorType.DOCUMENT_NOT_FOUND),
    KnownError(DocumentNotIndexedError, HTTPStatus.NOT_FOUND, ErrorType.DOCUMENT_NOT_FOUND),
    KnownError(DocumentVersionNotFoundError, HTTPStatus.NOT_FOUND, ErrorType.VERSION_NOT_FOUND),
    KnownError(StaleVersionError, HTTPStatus.PRECONDITION_FAILED, ErrorType.PRECONDITION_FAILED),
    KnownError(
        PreconditionFailedError, HTTPStatus.PRECONDITION_FAILED, ErrorType.PRECONDITION_FAILED
    ),
    KnownError(
        PreconditionRequiredError,
        HTTPStatus.PRECONDITION_REQUIRED,
        ErrorType.PRECONDITION_REQUIRED,
    ),
)


def register_error_handlers(app: FastAPI) -> None:
    """Map each failure class onto the JSON error body."""
    for known_error in KNOWN_ERRORS:
        app.add_exception_handler(
            known_error.exception_class, build_known_error_handler(known_error)
        )
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(HTTPException, handle_http_exception)
    app.add_exception_handler(Exception, handle_unexpected_error)


def build_known_error_handler(
    known_error: KnownError,
) -> Callable[[Request, Exception], JSONResponse]:
    """Return a handler that logs this error and responds with its status and type."""

    def handle_known_error(request: Request, error: Exception) -> JSONResponse:
        """Log the failure and return its status and type."""
        logger.warning(
            f"Request failed with {known_error.error_type} for {request.url.path}: "
            f"{type(error).__name__}"
        )
        return build_error_response(known_error.status, known_error.error_type, str(error))

    return handle_known_error


def handle_validation_error(request: Request, error: Exception) -> JSONResponse:
    """Return 422 for a request FastAPI could not validate."""
    if not isinstance(error, RequestValidationError):
        return handle_unexpected_error(request, error)
    validation = get_validation_summary(error)
    logger.warning(
        f"Rejected request at {validation.location} with error type {validation.error_kind}"
    )
    return build_error_response(
        HTTPStatus.UNPROCESSABLE_CONTENT,
        ErrorType.VALIDATION_ERROR,
        validation.summary,
    )


def handle_http_exception(request: Request, error: Exception) -> JSONResponse:
    """Return the status Starlette chose, in our error body."""
    if not isinstance(error, HTTPException):
        return handle_unexpected_error(request, error)
    phrase = get_reason_phrase(error.status_code)
    logger.warning(f"HTTP {error.status_code} for {request.url.path}")
    return build_error_response(error.status_code, ErrorType.HTTP_ERROR, phrase)


def handle_unexpected_error(request: Request, error: Exception) -> JSONResponse:
    """Return 500 without revealing the exception text."""
    token = request_id_context.set(get_request_id(request))
    try:
        logger.exception(f"Unhandled error for {request.url.path}")
    finally:
        request_id_context.reset(token)
    response = build_error_response(
        HTTPStatus.INTERNAL_SERVER_ERROR,
        ErrorType.INTERNAL_ERROR,
        INTERNAL_ERROR_MESSAGE,
    )
    response.headers[REQUEST_ID_HEADER] = get_request_id(request)
    return response


def build_error_response(
    status: HTTPStatus | int, error_type: ErrorType, message: str
) -> JSONResponse:
    """Build the JSON body every error returns."""
    status_code = int(status)
    body = ErrorResponse(error=message, code=status_code, error_type=error_type)
    return JSONResponse(status_code=status_code, content=asdict(body))


def get_validation_summary(error: RequestValidationError) -> ValidationSummary:
    """Return the location, error kind, and client summary of the first failure."""
    details = error.errors()
    if not details:
        return ValidationSummary(
            location=VALIDATION_LOCATION,
            error_kind=VALIDATION_ERROR_KIND,
            summary=INVALID_REQUEST_SUMMARY,
        )
    first = details[0]
    if "loc" not in first or "msg" not in first or "type" not in first:
        logger.error("Validation error is missing loc, msg, or type")
        return ValidationSummary(
            location=VALIDATION_LOCATION,
            error_kind=VALIDATION_ERROR_KIND,
            summary=INVALID_REQUEST_SUMMARY,
        )
    location = ".".join(str(part) for part in first["loc"])
    return ValidationSummary(
        location=location,
        error_kind=str(first["type"]),
        summary=f"{location}: {first['msg']}",
    )


def get_reason_phrase(status_code: int) -> str:
    """Return the standard phrase for an HTTP status."""
    try:
        return HTTPStatus(status_code).phrase
    except ValueError:
        logger.error(f"Unknown HTTP status {status_code}")
        return UNKNOWN_STATUS_PHRASE


def get_request_id(request: Request) -> str:
    """Return the request id stored by middleware, or the current context value."""
    state = request.scope.get("state", {})
    if "request_id" in state:
        return str(state["request_id"])
    return request_id_context.get()
