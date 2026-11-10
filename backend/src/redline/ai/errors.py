from enum import StrEnum


class ModelResponseFailure(StrEnum):
    """Why a model response cannot be used."""

    TRUNCATED = "truncated"
    REFUSED = "refused"
    INVALID_JSON = "invalid_json"
    MISSING_FIELD = "missing_field"


class AiError(Exception):
    """Base class for AI redline failures."""


class AiNotConfiguredError(AiError):
    """No API key is configured."""

    def __init__(self) -> None:
        """Build a readable message."""
        super().__init__("AI redlines are not configured")


class ModelUnavailableError(AiError):
    """The model API call failed."""

    def __init__(self, cause_name: str) -> None:
        """Store the SDK exception class name."""
        self.cause_name = cause_name
        super().__init__(cause_name)


class ModelResponseError(AiError):
    """The model responded, but the output cannot be used."""

    def __init__(self, reason: ModelResponseFailure) -> None:
        """Store why the output cannot be used."""
        self.reason = reason
        super().__init__(reason.value)
