"""Discovery Specialist Agent: Discovers tools from WebMCP & Remote MCP sources."""
from typing import Any, Dict, List
from backend.models.tool import ToolDefinition
from backend.protocols.messages import DiscoveryQueryMessage, DiscoveryResultMessage
from backend.registry.provider_registry import provider_registry
from backend.registry.tool_registry import tool_registry


class DiscoveryAgent:
    def __init__(self):
        self.agent_name = "discovery_agent"

    def discover_active_tools(self, msg: DiscoveryQueryMessage) -> DiscoveryResultMessage:
        all_tools = tool_registry.list_all_tools()
        active_providers = [p.provider_id for p in provider_registry.list_providers(healthy_only=True)]

        return DiscoveryResultMessage(
            correlation_id=msg.correlation_id,
            sender_agent=self.agent_name,
            target_agent="routing_agent",
            discovered_tools_count=len(all_tools),
            active_providers=active_providers
        )


discovery_agent = DiscoveryAgent()
