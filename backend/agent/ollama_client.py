"""Synchronous Ollama structured chat boundary."""

import logging
import time
from typing import Protocol, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from backend.agent.config import AgentSettings
from backend.agent.errors import (
    MODEL_HTTP_ERROR,
    MODEL_INVALID_RESPONSE,
    MODEL_NOT_FOUND,
    MODEL_TIMEOUT,
    MODEL_UNAVAILABLE,
    AgentExecutionError,
)
from backend.agent.schemas import ChatMessage


T = TypeVar("T", bound=BaseModel)
logger = logging.getLogger(__name__)

_CORRECTIVE_MESSAGE = (
    "Your previous response was invalid. Return only valid JSON that conforms "
    "to the supplied schema."
)


class ChatClient(Protocol):
    def chat(self, messages: list[ChatMessage], response_model: type[T]) -> T: ...


class OllamaClient:
    def __init__(self, settings: AgentSettings, client: httpx.Client | None = None) -> None:
        self.settings = settings
        self._client = client

    def chat(self, messages: list[ChatMessage], response_model: type[T]) -> T:
        started = time.monotonic()
        error_class = "none"
        try:
            return self._chat(messages, response_model)
        except AgentExecutionError as exc:
            error_class = exc.code
            raise
        finally:
            logger.info(
                "ollama_chat endpoint=api_chat model=%s duration_ms=%.1f error_class=%s",
                self.settings.model,
                (time.monotonic() - started) * 1000,
                error_class,
            )

    def _chat(self, messages: list[ChatMessage], response_model: type[T]) -> T:
        request_messages = [message.model_dump() for message in messages]
        schema = response_model.model_json_schema()
        client = self._client or httpx.Client()
        try:
            for attempt in range(2):
                response = self._post(client, request_messages, schema)
                content = self._content(response)
                try:
                    return response_model.model_validate_json(content)
                except ValidationError as exc:
                    if attempt == 1:
                        raise AgentExecutionError(
                            MODEL_INVALID_RESPONSE,
                            "El modelo devolvió una respuesta inválida.",
                        ) from exc
                    request_messages.extend(
                        [
                            {"role": "assistant", "content": content},
                            {"role": "user", "content": _CORRECTIVE_MESSAGE},
                        ]
                    )
        finally:
            if self._client is None:
                client.close()
        raise AssertionError("unreachable")

    def _post(self, client: httpx.Client, messages: list[dict[str, str]], schema: dict) -> httpx.Response:
        try:
            response = client.post(
                f"{self.settings.host}/api/chat",
                json={
                    "model": self.settings.model,
                    "messages": messages,
                    "stream": False,
                    "format": schema,
                },
                timeout=self.settings.timeout,
            )
        except httpx.TimeoutException as exc:
            raise AgentExecutionError(MODEL_TIMEOUT, "Se agotó el tiempo de espera del modelo.") from exc
        except httpx.TransportError as exc:
            raise AgentExecutionError(MODEL_UNAVAILABLE, "No se pudo contactar al modelo.") from exc

        if response.status_code == 404:
            raise AgentExecutionError(MODEL_NOT_FOUND, "No se encontró el modelo configurado.")
        if not response.is_success:
            raise AgentExecutionError(MODEL_HTTP_ERROR, "El servicio del modelo devolvió un error.")
        return response

    @staticmethod
    def _content(response: httpx.Response) -> str:
        try:
            envelope = response.json()
        except ValueError as exc:
            raise AgentExecutionError(MODEL_INVALID_RESPONSE, "El modelo devolvió una respuesta inválida.") from exc
        if not isinstance(envelope, dict):
            raise AgentExecutionError(MODEL_INVALID_RESPONSE, "El modelo devolvió una respuesta inválida.")
        message = envelope.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            raise AgentExecutionError(MODEL_INVALID_RESPONSE, "El modelo devolvió una respuesta inválida.")
        return content
