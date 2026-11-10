import logging
from contextvars import ContextVar

from redline.config import LOG_LEVEL_VARIABLE

NO_REQUEST_ID = "-"
REQUEST_ID_HEADER = "X-Request-ID"
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s [request %(request_id)s] %(message)s"
REDLINE_LOG_HANDLER = "redline"
request_id_context: ContextVar[str] = ContextVar("request_id", default=NO_REQUEST_ID)
_request_id_factory_installed = False


class RequestIdFilter(logging.Filter):
    """Puts the current request id on each log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Set the request id and keep the record."""
        record.request_id = request_id_context.get()
        return True


def configure_logging(log_level: str) -> None:
    """Send the root logger to stderr with the request id on every line."""
    level_names = logging.getLevelNamesMapping()
    if log_level not in level_names:
        raise RuntimeError(f"Environment variable {LOG_LEVEL_VARIABLE} is not a logging level")
    install_request_id_factory()
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    if not any(handler.name == REDLINE_LOG_HANDLER for handler in root_logger.handlers):
        handler = logging.StreamHandler()
        handler.addFilter(RequestIdFilter())
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        handler.name = REDLINE_LOG_HANDLER
        root_logger.addHandler(handler)


def install_request_id_factory() -> None:
    """Set the request id when a log record is created, so every handler can see it."""
    global _request_id_factory_installed
    if _request_id_factory_installed:
        return
    current_factory = logging.getLogRecordFactory()

    def factory(*args: object, **kwargs: object) -> logging.LogRecord:
        """Build a log record and attach the current request id."""
        record = current_factory(*args, **kwargs)
        record.request_id = request_id_context.get()
        return record

    logging.setLogRecordFactory(factory)
    _request_id_factory_installed = True
