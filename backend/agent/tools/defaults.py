"""Default deterministic tool catalog for ClaimGuard."""

from backend.agent.tools.audit_tool import audit_tool
from backend.agent.tools.claim_tool import claim_tool
from backend.agent.tools.registry import ToolRegistry
from backend.agent.tools.tariff_tool import tariff_tool


def build_default_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(claim_tool())
    registry.register(tariff_tool())
    registry.register(audit_tool())
    return registry
