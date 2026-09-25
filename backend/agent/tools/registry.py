"""Explicit registry for agent tools."""

import logging
from dataclasses import dataclass
from time import perf_counter
from typing import Callable

from pydantic import BaseModel, ValidationError

from backend.agent.schemas import AgentError, ToolCall, ToolResult


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    handler: Callable[[BaseModel], BaseModel | dict[str, object]]


class ToolExecutionError(Exception):
    """A handler's intentionally public, structured domain failure."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class ToolRegistry:
    def __init__(self) -> None:
        self._definitions: dict[str, ToolDefinition] = {}

    def register(self, definition: ToolDefinition) -> None:
        if definition.name in self._definitions:
            raise ValueError("tool already registered")
        self._definitions[definition.name] = definition

    def describe(self) -> list[dict[str, object]]:
        return [
            {
                "name": definition.name,
                "description": definition.description,
                "input_schema": definition.input_model.model_json_schema(),
                "output_schema": definition.output_model.model_json_schema(),
            }
            for definition in self._definitions.values()
        ]

    def execute(self, call: ToolCall) -> ToolResult:
        started = perf_counter()
        definition = self._definitions.get(call.name)

        def result(*, output: dict[str, object] | None = None, error: AgentError | None = None) -> ToolResult:
            duration_ms = (perf_counter() - started) * 1000
            category = error.code if error else "success"
            # Unknown names and all payloads are untrusted; never include them in logs.
            logger.info(
                "Tool execution tool=%s duration_ms=%.3f category=%s",
                definition.name if definition else "<unknown>",
                duration_ms,
                category,
            )
            return ToolResult(
                call_id=call.call_id,
                tool=call.name,
                status="error" if error else "success",
                output=output,
                error=error,
                duration_ms=duration_ms,
            )

        if definition is None:
            return result(error=AgentError(code="unknown_tool", message="Unknown tool"))

        try:
            arguments = definition.input_model.model_validate(call.arguments)
        except ValidationError:
            return result(error=AgentError(code="invalid_arguments", message="Invalid tool arguments"))
        except Exception:
            return result(error=AgentError(code="invalid_arguments", message="Invalid tool arguments"))

        try:
            raw_output = definition.handler(arguments)
        except ToolExecutionError as exc:
            return result(error=AgentError(code=exc.code, message=exc.message))
        except Exception:
            return result(error=AgentError(code="tool_failure", message="Tool execution failed"))

        try:
            if isinstance(raw_output, BaseModel):
                raw_output = raw_output.model_dump(mode="python")
            if not isinstance(raw_output, dict):
                raise ValueError("tool output must be a mapping")
            validated_output = definition.output_model.model_validate(raw_output)
            output = validated_output.model_dump(mode="json")
        except Exception:
            return result(error=AgentError(code="invalid_tool_output", message="Invalid tool output"))

        return result(output=output)
