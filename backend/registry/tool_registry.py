"""Dynamic Tool Registry for WebMCP and Remote MCP tools."""
import logging
import time
from typing import Any, Dict, List, Optional
from backend.models.tool import ToolDefinition, ToolStatus
from backend.registry.capability_map import CAPABILITY_DEFINITIONS, CanonicalCapability

logger = logging.getLogger("Registry.ToolRegistry")


class ToolRegistry:
    def __init__(self):
        # tool_id -> ToolDefinition
        self._tools: Dict[str, ToolDefinition] = {}

    def register_tool(self, tool: ToolDefinition) -> None:
        """Register or update a tool in the canonical registry."""
        if tool.canonical_capability not in CAPABILITY_DEFINITIONS:
            raise ValueError(f"Unknown canonical capability: {tool.canonical_capability}")

        self._tools[tool.tool_id] = tool
        logger.info(f"Registered tool '{tool.tool_name}' ({tool.tool_id}) from provider '{tool.provider_id}' as '{tool.canonical_capability}'.")

    def unregister_tool(self, tool_id: str) -> bool:
        if tool_id in self._tools:
            del self._tools[tool_id]
            logger.info(f"Unregistered tool '{tool_id}'.")
            return True
        return False

    def mark_provider_tools_status(self, provider_id: str, status: ToolStatus) -> int:
        """Update availability status of all tools belonging to a provider."""
        count = 0
        for tool in self._tools.values():
            if tool.provider_id == provider_id:
                tool.status = status
                count += 1
        logger.info(f"Updated {count} tools for provider '{provider_id}' to status '{status.value}'.")
        return count

    def get_tool(self, tool_id: str) -> Optional[ToolDefinition]:
        return self._tools.get(tool_id)

    def find_tools_by_capability(
        self,
        capability: str,
        active_only: bool = True
    ) -> List[ToolDefinition]:
        """Query all tools implementing a specific canonical capability."""
        matches = []
        for tool in self._tools.values():
            if tool.canonical_capability == capability:
                if active_only and tool.status != ToolStatus.AVAILABLE:
                    continue
                matches.append(tool)
        return matches

    def find_tool_for_provider(
        self,
        provider_id: str,
        capability: str
    ) -> Optional[ToolDefinition]:
        """Find a specific provider's tool implementing a capability."""
        for tool in self._tools.values():
            if tool.provider_id == provider_id and tool.canonical_capability == capability:
                if tool.status == ToolStatus.AVAILABLE:
                    return tool
        return None

    def find_tools(
        self,
        capability: str,
        provider_id: Optional[str] = None,
        active_only: bool = True
    ) -> List[ToolDefinition]:
        """Convenience query for tools by capability and optional provider filter."""
        matches = self.find_tools_by_capability(capability, active_only=active_only)
        if provider_id:
            matches = [t for t in matches if t.provider_id == provider_id]
        return matches

    def list_all_tools(self) -> List[ToolDefinition]:
        return list(self._tools.values())

    def clear(self) -> None:
        self._tools.clear()


# Global tool registry singleton
tool_registry = ToolRegistry()
