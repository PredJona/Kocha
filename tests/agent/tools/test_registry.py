import logging

import pytest
from pydantic import BaseModel, ConfigDict, Field

from backend.agent.schemas import ToolCall
from backend.agent.tools.registry import ToolDefinition, ToolExecutionError, ToolRegistry


class AddInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: int = Field(strict=True, ge=0)


class AddOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result: int


def definition(handler):
    return ToolDefinition(
        name="add_one",
        description="Add one to a nonnegative integer",
        input_model=AddInput,
        output_model=AddOutput,
        handler=handler,
    )


def call(name="add_one", arguments=None):
    return ToolCall(call_id="call-123", name=name, arguments={"value": 4} if arguments is None else arguments)


def test_registered_tool_is_described_with_both_json_schemas():
    registry = ToolRegistry()
    registry.register(definition(lambda request: {"result": request.value + 1}))

    assert registry.describe() == [
        {
            "name": "add_one",
            "description": "Add one to a nonnegative integer",
            "input_schema": AddInput.model_json_schema(),
            "output_schema": AddOutput.model_json_schema(),
        }
    ]


def test_duplicate_registration_does_not_replace_existing_handler():
    registry = ToolRegistry()
    registry.register(definition(lambda request: {"result": request.value + 1}))

    with pytest.raises(ValueError):
        registry.register(definition(lambda request: {"result": 999}))

    assert registry.execute(call()).output == {"result": 5}


def test_unknown_tool_is_rejected_without_dispatch_or_logging_untrusted_name(caplog):
    registry = ToolRegistry()
    registry.register(definition(lambda request: {"result": request.value + 1}))
    caplog.set_level(logging.INFO)
    malicious_name = "add_one; secret-payload"

    result = registry.execute(call(name=malicious_name))

    assert result.call_id == "call-123"
    assert result.tool == malicious_name
    assert result.status == "error"
    assert result.error.code == "unknown_tool"
    assert result.output is None
    assert result.duration_ms >= 0
    assert malicious_name not in caplog.text
    assert "unknown_tool" in caplog.text


@pytest.mark.parametrize("arguments", [{"value": -1}, {"value": "4"}, {"value": 4, "extra": "secret"}])
def test_invalid_arguments_are_rejected_before_handler(arguments):
    invocations = []

    def handler(request):
        invocations.append(request)
        return {"result": request.value + 1}

    registry = ToolRegistry()
    registry.register(definition(handler))

    result = registry.execute(call(arguments=arguments))

    assert result.status == "error"
    assert result.error.code == "invalid_arguments"
    assert result.output is None
    assert result.duration_ms >= 0
    assert invocations == []


@pytest.mark.parametrize("returned", [{"result": 5}, AddOutput(result=5)])
def test_execution_passes_validated_model_and_returns_validated_output(returned):
    received = []

    def handler(request):
        received.append(request)
        return returned

    registry = ToolRegistry()
    registry.register(definition(handler))

    result = registry.execute(call())

    assert received == [AddInput(value=4)]
    assert result.call_id == "call-123"
    assert result.tool == "add_one"
    assert result.status == "success"
    assert result.output == {"result": 5}
    assert result.error is None
    assert result.duration_ms >= 0


def test_handler_failure_returns_generic_error_without_leaking_private_data(caplog):
    def handler(request):
        raise RuntimeError("secret invoice 999")

    registry = ToolRegistry()
    registry.register(definition(handler))
    caplog.set_level(logging.INFO)

    result = registry.execute(call(arguments={"value": 4, "private": "secret input"}))
    assert result.error.code == "invalid_arguments"

    result = registry.execute(call())

    assert result.status == "error"
    assert result.error.code == "tool_failure"
    assert "secret invoice 999" not in result.error.message
    assert "secret invoice 999" not in caplog.text
    assert "secret input" not in caplog.text
    assert result.duration_ms >= 0


def test_domain_error_exposes_only_explicit_safe_code_and_message():
    def handler(request):
        raise ToolExecutionError("claim_not_found", "Claim was not found")

    registry = ToolRegistry()
    registry.register(definition(handler))

    result = registry.execute(call())

    assert result.status == "error"
    assert result.error.code == "claim_not_found"
    assert result.error.message == "Claim was not found"


@pytest.mark.parametrize("returned", [{"result": "not-a-number"}, {"wrong": 5}, {"result": 5, "extra": 1}, 5])
def test_invalid_handler_output_returns_controlled_error(returned):
    registry = ToolRegistry()
    registry.register(definition(lambda request: returned))

    result = registry.execute(call())

    assert result.status == "error"
    assert result.error.code == "invalid_tool_output"
    assert result.output is None
    assert result.duration_ms >= 0
