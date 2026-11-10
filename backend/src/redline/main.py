import logging
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from redline.ai.model_client import build_model_client
from redline.ai.playbook import PLAYBOOK_PATH, load_playbook
from redline.api.error_handlers import register_error_handlers
from redline.api.routes.ai_redlines import router as ai_redlines_router
from redline.api.routes.documents import router as documents_router
from redline.api.routes.health import router as health_router
from redline.api.routes.search import router as search_router
from redline.config import Settings, load_settings
from redline.logging_setup import configure_logging, request_id_context
from redline.services.search_service import SearchService
from redline.storage.database import apply_schema, open_connection_pool
from redline.storage.document_repository import list_current_documents

logger = logging.getLogger(__name__)

MAXIMUM_REQUEST_ID_LENGTH = 64
REQUEST_ID_HEADER_NAME = b"x-request-id"


class RequestIdMiddleware:
    """Sets the request id for the rest of the request and echoes it back."""

    def __init__(self, app: ASGIApp) -> None:
        """Store the next ASGI app."""
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Attach a request id, then call the next app."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = scope.get("headers", [])
        supplied_request_id = get_accepted_request_id(headers)
        request_id = supplied_request_id if supplied_request_id is not None else uuid.uuid4().hex
        state = scope.get("state", {})
        state["request_id"] = request_id
        scope["state"] = state
        token = request_id_context.set(request_id)
        try:
            await self.app(scope, receive, send_with_request_id(send, request_id))
        finally:
            request_id_context.reset(token)


def create_app(settings: Settings) -> FastAPI:
    """Build the API, including logging, the database pool, and the routes."""
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        """Open the database pool for the process, then close it."""
        logger.info("Starting the server")
        pool = open_connection_pool(settings.database_url)
        try:
            with pool.connection() as connection:
                apply_schema(connection)
                documents = list_current_documents(connection)
            search_service = SearchService()
            started = time.perf_counter()
            search_service.load_documents(documents)
            elapsed = time.perf_counter() - started
            app.state.connection_pool = pool
            app.state.search_service = search_service
            app.state.playbook = load_playbook(PLAYBOOK_PATH)
            app.state.model_client = build_model_client(settings)
            if settings.anthropic_api_key is None:
                logger.info("AI redlines are not configured")
            else:
                logger.info("AI redlines are configured")
            logger.info(f"Indexed {len(documents)} documents in {elapsed:.3f} seconds")
            logger.info("Started the server")
            yield
        finally:
            pool.close()
            logger.info("Stopped the server")

    app = FastAPI(lifespan=lifespan)
    app.add_middleware(RequestIdMiddleware)
    register_error_handlers(app)
    app.include_router(documents_router)
    app.include_router(search_router)
    app.include_router(ai_redlines_router)
    app.include_router(health_router)
    return app


def build_app() -> FastAPI:
    """Build the app from the environment."""
    return create_app(load_settings())


def get_accepted_request_id(headers: list[tuple[bytes, bytes]]) -> str | None:
    """Return a usable X-Request-ID header, or None when it should be replaced."""
    for name, value in headers:
        if name.lower() != REQUEST_ID_HEADER_NAME:
            continue
        text = value.decode("latin-1")
        if is_accepted_request_id(text):
            return text
        return None
    return None


def is_accepted_request_id(value: str) -> bool:
    """Return whether a caller-supplied request id is short and has no whitespace."""
    if len(value) > MAXIMUM_REQUEST_ID_LENGTH:
        return False
    return not any(character.isspace() for character in value)


def send_with_request_id(send: Send, request_id: str) -> Send:
    """Return a send function that adds the request id to the response."""

    async def send_message(message: Message) -> None:
        """Add the request id when the response starts."""
        if message["type"] == "http.response.start":
            response_headers = list(message["headers"])
            response_headers.append((REQUEST_ID_HEADER_NAME, request_id.encode("latin-1")))
            message = {**message, "headers": response_headers}
        await send(message)

    return send_message
