import json
from dataclasses import dataclass

import anthropic
import pytest

from redline.ai.errors import (
    AiNotConfiguredError,
    ModelResponseError,
    ModelResponseFailure,
    ModelUnavailableError,
)
from redline.ai.model_client import (
    JSON_SCHEMA_FORMAT,
    USER_MESSAGE_ROLE,
    AnthropicModelClient,
    UnconfiguredModelClient,
    build_model_client,
    parse_suggestions,
)
from redline.ai.prompts import (
    EFFORT_LEVEL,
    MAXIMUM_OUTPUT_TOKENS,
    MODEL_NAME,
    SUGGESTIONS_SCHEMA,
    THINKING_SETTING,
)
from redline.config import Settings

SYSTEM_PROMPT = "Review for the customer."
USER_PROMPT = "Make the indemnification mutual."
SUGGESTION_JSON = {
    "text": "indemnify",
    "prefix": "shall ",
    "suffix": " the",
    "replacement": "defend",
    "rationale": "Mutual indemnity.",
}


@dataclass
class ContentBlock:
    """One stand-in response block."""

    type: str
    text: str


@dataclass
class Usage:
    """Stand-in token counts."""

    input_tokens: int
    output_tokens: int


@dataclass
class ModelResponse:
    """A stand-in for the SDK message."""

    stop_reason: str
    content: list[ContentBlock]
    usage: Usage


class SampleAPIError(anthropic.APIError):
    """An API error that does not need a live HTTP request."""

    def __init__(self) -> None:
        """Store a class name the client can log."""
        self.message = "failed"


def test_request_sends_model_schema_thinking_effort_and_prompts() -> None:
    """The request carries the model, schema, thinking setting, effort, and prompts."""
    client = AnthropicModelClient("test-key")
    recorded: dict[str, object] = {}

    def create(**kwargs: object) -> ModelResponse:
        """Record the request and return one suggestion."""
        recorded.update(kwargs)
        return suggestion_response("end_turn")

    client.anthropic_client.messages.create = create

    suggestions = client.request_suggestions(SYSTEM_PROMPT, USER_PROMPT)

    assert recorded["model"] == MODEL_NAME
    assert recorded["max_tokens"] == MAXIMUM_OUTPUT_TOKENS
    assert recorded["system"] == SYSTEM_PROMPT
    assert recorded["messages"] == [{"role": USER_MESSAGE_ROLE, "content": USER_PROMPT}]
    assert recorded["thinking"] == THINKING_SETTING
    output_config = recorded["output_config"]
    assert isinstance(output_config, dict)
    assert output_config["effort"] == EFFORT_LEVEL
    output_format = output_config["format"]
    assert isinstance(output_format, dict)
    assert output_format["type"] == JSON_SCHEMA_FORMAT
    assert output_format["schema"] == SUGGESTIONS_SCHEMA
    assert suggestions[0].text == "indemnify"


def test_response_without_text_block_raises_model_response_error() -> None:
    """A response that has no text block cannot be parsed."""
    client = AnthropicModelClient("test-key")
    response = ModelResponse(
        stop_reason="end_turn",
        content=[ContentBlock(type="thinking", text="")],
        usage=Usage(input_tokens=1, output_tokens=1),
    )
    client.anthropic_client.messages.create = lambda **kwargs: response

    with pytest.raises(ModelResponseError) as raised:
        client.request_suggestions(SYSTEM_PROMPT, USER_PROMPT)

    assert raised.value.reason == ModelResponseFailure.INVALID_JSON


def test_end_turn_response_parses_suggestions() -> None:
    """An end_turn response uses the text block and ignores a thinking block."""
    client = AnthropicModelClient("test-key")
    client.anthropic_client.messages.create = lambda **kwargs: suggestion_response("end_turn")

    suggestions = client.request_suggestions(SYSTEM_PROMPT, USER_PROMPT)

    assert len(suggestions) == 1
    assert suggestions[0].replacement == "defend"
    assert suggestions[0].rationale == "Mutual indemnity."


def test_max_tokens_stop_reason_raises_model_response_error() -> None:
    """A truncated response is rejected."""
    client = AnthropicModelClient("test-key")
    client.anthropic_client.messages.create = lambda **kwargs: suggestion_response("max_tokens")

    with pytest.raises(ModelResponseError) as raised:
        client.request_suggestions(SYSTEM_PROMPT, USER_PROMPT)

    assert raised.value.reason == ModelResponseFailure.TRUNCATED


def test_refusal_stop_reason_raises_model_response_error() -> None:
    """A refusal is rejected."""
    client = AnthropicModelClient("test-key")
    client.anthropic_client.messages.create = lambda **kwargs: suggestion_response("refusal")

    with pytest.raises(ModelResponseError) as raised:
        client.request_suggestions(SYSTEM_PROMPT, USER_PROMPT)

    assert raised.value.reason == ModelResponseFailure.REFUSED


def test_api_error_raises_model_unavailable_error() -> None:
    """An SDK error becomes a model-unavailable error named by the SDK class."""
    client = AnthropicModelClient("test-key")

    def create(**kwargs: object) -> ModelResponse:
        """Raise an SDK error."""
        raise SampleAPIError()

    client.anthropic_client.messages.create = create

    with pytest.raises(ModelUnavailableError) as raised:
        client.request_suggestions(SYSTEM_PROMPT, USER_PROMPT)

    assert raised.value.cause_name == "SampleAPIError"


def test_parse_suggestions_with_invalid_json_raises_model_response_error() -> None:
    """Text that is not JSON is rejected."""
    with pytest.raises(ModelResponseError) as raised:
        parse_suggestions("not json")

    assert raised.value.reason == ModelResponseFailure.INVALID_JSON


def test_parse_suggestions_with_missing_field_raises_model_response_error() -> None:
    """A suggestion missing a field is rejected."""
    with pytest.raises(ModelResponseError) as raised:
        parse_suggestions(json.dumps({"suggestions": [{"text": "indemnify"}]}))

    assert raised.value.reason == ModelResponseFailure.MISSING_FIELD


def test_unconfigured_client_raises_ai_not_configured_error() -> None:
    """A client with no key refuses the request."""
    with pytest.raises(AiNotConfiguredError):
        UnconfiguredModelClient().request_suggestions(SYSTEM_PROMPT, USER_PROMPT)


def test_build_model_client_without_key_is_unconfigured() -> None:
    """No API key builds the unconfigured client."""
    settings = Settings(
        database_url="postgresql://example", log_level="INFO", anthropic_api_key=None
    )

    client = build_model_client(settings)

    assert isinstance(client, UnconfiguredModelClient)


def test_build_model_client_with_key_is_anthropic() -> None:
    """A key builds the Anthropic client."""
    settings = Settings(
        database_url="postgresql://example", log_level="INFO", anthropic_api_key="test-key"
    )

    client = build_model_client(settings)

    assert isinstance(client, AnthropicModelClient)


def suggestion_response(stop_reason: str) -> ModelResponse:
    """Build a response whose text block is one suggestion."""
    return ModelResponse(
        stop_reason=stop_reason,
        content=[
            ContentBlock(type="thinking", text="not json"),
            ContentBlock(
                type="text",
                text=json.dumps({"suggestions": [SUGGESTION_JSON]}),
            ),
        ],
        usage=Usage(input_tokens=12, output_tokens=8),
    )
