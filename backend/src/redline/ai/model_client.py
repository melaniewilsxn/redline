import json
import logging
import time
from typing import Protocol

import anthropic

from redline.ai.errors import (
    AiNotConfiguredError,
    ModelResponseError,
    ModelResponseFailure,
    ModelUnavailableError,
)
from redline.ai.models import RedlineSuggestion
from redline.ai.prompts import (
    EFFORT_LEVEL,
    MAXIMUM_OUTPUT_TOKENS,
    MODEL_NAME,
    PREFIX_FIELD,
    RATIONALE_FIELD,
    REPLACEMENT_FIELD,
    SUFFIX_FIELD,
    SUGGESTIONS_SCHEMA,
    TEXT_FIELD,
    THINKING_SETTING,
)
from redline.config import Settings

logger = logging.getLogger(__name__)

MODEL_TIMEOUT_SECONDS = 90
MODEL_MAXIMUM_RETRIES = 2
USER_MESSAGE_ROLE = "user"
JSON_SCHEMA_FORMAT = "json_schema"
TEXT_BLOCK_TYPE = "text"
MAX_TOKENS_STOP_REASON = "max_tokens"
REFUSAL_STOP_REASON = "refusal"
SUGGESTIONS_KEY = "suggestions"


class ModelContentBlock(Protocol):
    """One block in a model response."""

    type: str
    text: str


class RedlineModelClient(Protocol):
    """Asks a model for redline suggestions."""

    def request_suggestions(self, system_prompt: str, user_prompt: str) -> list[RedlineSuggestion]:
        """Return the model's suggestions for this prompt."""
        ...


class AnthropicModelClient:
    """Requests suggestions from Claude with schema-constrained output."""

    def __init__(self, api_key: str) -> None:
        """Open an SDK client. The key is not logged."""
        self.anthropic_client = anthropic.Anthropic(
            api_key=api_key,
            timeout=MODEL_TIMEOUT_SECONDS,
            max_retries=MODEL_MAXIMUM_RETRIES,
        )

    def request_suggestions(self, system_prompt: str, user_prompt: str) -> list[RedlineSuggestion]:
        """Send one prompt and return the parsed suggestions."""
        prompt_length = len(system_prompt) + len(user_prompt)
        logger.info(f"Started model request, prompt length {prompt_length}")
        started = time.perf_counter()
        try:
            response = self.anthropic_client.messages.create(
                model=MODEL_NAME,
                max_tokens=MAXIMUM_OUTPUT_TOKENS,
                system=system_prompt,
                messages=[{"role": USER_MESSAGE_ROLE, "content": user_prompt}],
                thinking=THINKING_SETTING,
                output_config={
                    "format": {"type": JSON_SCHEMA_FORMAT, "schema": SUGGESTIONS_SCHEMA},
                    "effort": EFFORT_LEVEL,
                },
            )
        except anthropic.APIError as error:
            cause_name = type(error).__name__
            logger.error(f"Model request failed with {cause_name}")
            raise ModelUnavailableError(cause_name) from None
        if response.stop_reason == MAX_TOKENS_STOP_REASON:
            logger.error(f"Model response was truncated after prompt length {prompt_length}")
            raise ModelResponseError(ModelResponseFailure.TRUNCATED)
        if response.stop_reason == REFUSAL_STOP_REASON:
            logger.error(f"Model refused the request after prompt length {prompt_length}")
            raise ModelResponseError(ModelResponseFailure.REFUSED)
        response_text = join_text_blocks(response.content)
        suggestions = parse_suggestions(response_text)
        elapsed = time.perf_counter() - started
        logger.info(
            f"Finished model request with stop reason {response.stop_reason}, "
            f"input tokens {response.usage.input_tokens}, "
            f"output tokens {response.usage.output_tokens}, "
            f"{elapsed:.3f} seconds, {len(suggestions)} suggestions"
        )
        return suggestions


class UnconfiguredModelClient:
    """Fails every request because no API key is configured."""

    def request_suggestions(self, system_prompt: str, user_prompt: str) -> list[RedlineSuggestion]:
        """Raise because no API key is configured."""
        logger.error(
            f"AI redlines are not configured, prompt length {len(system_prompt) + len(user_prompt)}"
        )
        raise AiNotConfiguredError()


def join_text_blocks(content: list[ModelContentBlock]) -> str:
    """Join the text blocks. A response with none cannot be parsed."""
    texts: list[str] = []
    for block in content:
        if block.type != TEXT_BLOCK_TYPE:
            continue
        texts.append(block.text)
    if not texts:
        logger.error("Model response had no text block")
        raise ModelResponseError(ModelResponseFailure.INVALID_JSON)
    return "".join(texts)


def parse_suggestions(response_text: str) -> list[RedlineSuggestion]:
    """Build suggestions from the model's JSON text."""
    try:
        payload = json.loads(response_text)
    except json.JSONDecodeError as error:
        logger.error(f"Model response was not JSON: {type(error).__name__}")
        raise ModelResponseError(ModelResponseFailure.INVALID_JSON) from None
    if not isinstance(payload, dict) or SUGGESTIONS_KEY not in payload:
        logger.error(f"Model response is missing {SUGGESTIONS_KEY}")
        raise ModelResponseError(ModelResponseFailure.MISSING_FIELD)
    suggestion_payloads = payload[SUGGESTIONS_KEY]
    if not isinstance(suggestion_payloads, list):
        logger.error("Model suggestions were not a list")
        raise ModelResponseError(ModelResponseFailure.INVALID_JSON)
    return [read_suggestion(suggestion_payload) for suggestion_payload in suggestion_payloads]


def read_suggestion(payload: object) -> RedlineSuggestion:
    """Build one suggestion, or raise when a field is missing."""
    if not isinstance(payload, dict):
        logger.error("A model suggestion was not an object")
        raise ModelResponseError(ModelResponseFailure.INVALID_JSON)
    return RedlineSuggestion(
        text=read_string_field(payload, TEXT_FIELD),
        prefix=read_string_field(payload, PREFIX_FIELD),
        suffix=read_string_field(payload, SUFFIX_FIELD),
        replacement=read_string_field(payload, REPLACEMENT_FIELD),
        rationale=read_string_field(payload, RATIONALE_FIELD),
    )


def read_string_field(payload: dict[str, object], key: str) -> str:
    """Return a string field, or raise when it is missing or not a string."""
    if key not in payload or not isinstance(payload[key], str):
        logger.error(f"A model suggestion is missing {key}")
        raise ModelResponseError(ModelResponseFailure.MISSING_FIELD)
    return payload[key]


def build_model_client(settings: Settings) -> RedlineModelClient:
    """Return an Anthropic client when a key is set, otherwise the unconfigured client."""
    if settings.anthropic_api_key is None:
        return UnconfiguredModelClient()
    return AnthropicModelClient(settings.anthropic_api_key)
