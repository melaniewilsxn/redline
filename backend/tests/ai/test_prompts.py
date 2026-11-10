from redline.ai.prompts import SUGGESTIONS_SCHEMA, build_user_prompt

INSTRUCTION = "Make the indemnification mutual"
PLAYBOOK_TEXT = "Represented party: Customer"
CONTRACT_TEXT = "The Customer shall indemnify the Company."


def test_user_prompt_wraps_instruction_playbook_and_contract() -> None:
    """The user prompt keeps the instruction, playbook, and contract in separate tags."""
    prompt = build_user_prompt(INSTRUCTION, PLAYBOOK_TEXT, CONTRACT_TEXT)

    instruction_at = prompt.index("<instruction>")
    playbook_at = prompt.index("<playbook>")
    contract_at = prompt.index("<contract>")
    assert instruction_at < playbook_at < contract_at
    assert INSTRUCTION in prompt
    assert PLAYBOOK_TEXT in prompt
    assert CONTRACT_TEXT in prompt
    assert "</instruction>" in prompt
    assert "</playbook>" in prompt
    assert "</contract>" in prompt


def test_schema_closes_every_object_and_requires_every_property() -> None:
    """Every object refuses extra fields and requires each of its properties."""
    assert_closed(SUGGESTIONS_SCHEMA)


def assert_closed(schema: object) -> None:
    """Check one schema node and the objects nested inside it."""
    if not isinstance(schema, dict):
        return
    if "type" in schema and schema["type"] == "object":
        assert schema["additionalProperties"] is False
        assert "properties" in schema
        assert "required" in schema
        properties = schema["properties"]
        assert isinstance(properties, dict)
        assert set(schema["required"]) == set(properties)
        for property_schema in properties.values():
            assert_closed(property_schema)
    if "items" in schema:
        assert_closed(schema["items"])
