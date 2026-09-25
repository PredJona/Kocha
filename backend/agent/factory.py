"""Production wiring for the agent boundary."""

from backend.agent.config import AgentSettings
from backend.agent.ollama_client import OllamaClient
from backend.agent.orchestrator import AgentOrchestrator
from backend.agent.tools.defaults import build_default_registry


def get_agent_orchestrator() -> AgentOrchestrator:
    return AgentOrchestrator(
        client=OllamaClient(AgentSettings.from_env()),
        registry=build_default_registry(),
    )
