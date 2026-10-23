"""Adapter for Live Browser WebMCP tool execution."""
import logging
from typing import Any, Dict, List
from backend.adapters.base_adapter import BaseProviderAdapter
from backend.bridge.browser_bridge import browser_bridge
from backend.models.provider import ProviderHealth, ProviderInfo, ProviderType
from backend.models.tool import ExecutionMode, ToolDefinition, ToolExecutionResult
from backend.registry.tool_registry import tool_registry

logger = logging.getLogger("Adapters.WebMCPAdapter")


class WebMCPBrowserAdapter(BaseProviderAdapter):
    def __init__(self, session_id: str, origin_url: str):
        self.session_id = session_id
        self.origin_url = origin_url
        self._provider_id = f"browser_{session_id}"

    @property
    def provider_info(self) -> ProviderInfo:
        session = browser_bridge._sessions.get(self.session_id)
        is_healthy = session is not None and session.is_active and not session.is_stale(browser_bridge.session_timeout)

        caps = []
        if session:
            caps = [t.canonical_capability for t in session.declared_tools.values()]

        return ProviderInfo(
            provider_id=self._provider_id,
            name=f"WebMCP Browser Tab ({self.session_id})",
            description=f"Active browser context at {self.origin_url}",
            provider_type=ProviderType.WEBMCP_SITE,
            origin_url=self.origin_url,
            supported_capabilities=list(set(caps)),
            health=ProviderHealth.HEALTHY if is_healthy else ProviderHealth.UNREACHABLE,
            data_quality_score=0.98,
            historical_reliability=0.99,
            average_latency_ms=45.0
        )

    def discover_tools(self) -> List[ToolDefinition]:
        """Query tools registered by this browser session in tool_registry."""
        tools = []
        for t in tool_registry.list_all_tools():
            if t.provider_id == self._provider_id:
                tools.append(t)
        return tools

    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> ToolExecutionResult:
        logger.info(f"Forwarding execution of '{tool_name}' to browser tab '{self.session_id}' via WebMCP bridge.")
        return browser_bridge.execute_in_browser(self.session_id, tool_name, arguments)

    def get_health(self) -> ProviderHealth:
        return self.provider_info.health
