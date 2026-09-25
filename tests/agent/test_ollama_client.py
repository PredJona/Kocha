import json

import httpx
import pytest

from backend.agent.config import AgentSettings
from backend.agent.errors import AgentExecutionError
from backend.agent.ollama_client import OllamaClient
from backend.agent.schemas import AgentDecision, ChatMessage, FinalDecision


MESSAGES = [ChatMessage(role="user", content="Review invoice")]


def response(content):
    return httpx.Response(200, json={"model": "any-model", "message": {"role": "assistant", "content": content}, "done": True})


def make_client(handler):
    settings = AgentSettings(host="http://ollama.test", model="another-model:latest", timeout=2.5)
    return OllamaClient(settings, client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_chat_sends_schema_and_returns_root_model():
    requests = []

    def handle(request):
        requests.append(request)
        return response('{"type":"final_answer","message":"Approved"}')

    decision = make_client(handle).chat(MESSAGES, AgentDecision)

    assert isinstance(decision, AgentDecision)
    assert isinstance(decision.root, FinalDecision)
    assert decision.root.message == "Approved"
    assert len(requests) == 1
    assert requests[0].method == "POST"
    assert str(requests[0].url) == "http://ollama.test/api/chat"
    assert json.loads(requests[0].content) == {
        "model": "another-model:latest",
        "messages": [{"role": "user", "content": "Review invoice"}],
        "stream": False,
        "format": AgentDecision.model_json_schema(),
        "options": {"temperature": 0},
    }


def test_invalid_inner_json_gets_one_corrective_retry_without_mutating_messages():
    requests = []
    replies = iter([response("{"), response('{"type":"final_answer","message":"Approved"}')])

    def handle(request):
        requests.append(json.loads(request.content))
        return next(replies)

    original = list(MESSAGES)
    decision = make_client(handle).chat(MESSAGES, AgentDecision)

    assert decision.root.message == "Approved"
    assert len(requests) == 2
    assert requests[0]["messages"] == [{"role": "user", "content": "Review invoice"}]
    assert requests[1]["messages"][:2] == [
        {"role": "user", "content": "Review invoice"},
        {"role": "assistant", "content": "{"},
    ]
    assert requests[1]["messages"][2]["role"] == "user"
    assert "JSON" in requests[1]["messages"][2]["content"]
    assert requests[1]["format"] == AgentDecision.model_json_schema()
    assert MESSAGES == original
    assert len(MESSAGES) == 1


@pytest.mark.parametrize("content", ["{", '{"type":"final_answer","message":"  "}'])
def test_invalid_structured_response_stops_after_two_attempts(content):
    calls = []

    def handle(request):
        calls.append(request)
        return response(content)

    with pytest.raises(AgentExecutionError) as exc:
        make_client(handle).chat(MESSAGES, AgentDecision)

    assert exc.value.code == "MODEL_INVALID_RESPONSE"
    assert len(calls) == 2
    assert content not in exc.value.message


@pytest.mark.parametrize(
    "bad_response",
    [
        httpx.Response(200, content="not outer json"),
        httpx.Response(200, json={"model": "any-model", "done": True}),
        httpx.Response(200, json={"message": None}),
        httpx.Response(200, json={"message": []}),
        httpx.Response(200, json={"message": {"role": "assistant"}}),
        httpx.Response(200, json={"message": {"role": "assistant", "content": 42}}),
        response("  \t "),
    ],
)
def test_malformed_envelope_or_content_is_public_safe_error_without_retry(bad_response):
    calls = []

    def handle(request):
        calls.append(request)
        return bad_response

    with pytest.raises(AgentExecutionError) as exc:
        make_client(handle).chat(MESSAGES, AgentDecision)

    assert exc.value.code == "MODEL_INVALID_RESPONSE"
    assert "not outer json" not in exc.value.message
    assert len(calls) == 1


def test_model_not_found_maps_to_public_error():
    with pytest.raises(AgentExecutionError) as exc:
        make_client(lambda _: httpx.Response(404, text="private model registry info")).chat(MESSAGES, AgentDecision)

    assert exc.value.code == "MODEL_NOT_FOUND"
    assert "private" not in exc.value.message


@pytest.mark.parametrize("status", [401, 429, 500])
def test_other_http_failure_maps_to_public_error(status):
    with pytest.raises(AgentExecutionError) as exc:
        make_client(lambda _: httpx.Response(status, text="secret backend detail")).chat(MESSAGES, AgentDecision)

    assert exc.value.code == "MODEL_HTTP_ERROR"
    assert "secret" not in exc.value.message


def test_connection_failure_maps_to_unavailable():
    def handle(request):
        raise httpx.ConnectError("secret host", request=request)

    with pytest.raises(AgentExecutionError) as exc:
        make_client(handle).chat(MESSAGES, AgentDecision)

    assert exc.value.code == "MODEL_UNAVAILABLE"
    assert "secret" not in exc.value.message


def test_timeout_maps_to_timeout():
    def handle(request):
        raise httpx.ReadTimeout("secret timeout", request=request)

    with pytest.raises(AgentExecutionError) as exc:
        make_client(handle).chat(MESSAGES, AgentDecision)

    assert exc.value.code == "MODEL_TIMEOUT"
    assert "secret" not in exc.value.message
