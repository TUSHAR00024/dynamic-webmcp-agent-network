"""Base Adapter Interface for Tool Providers in Dynamic WebMCP Agent Network."""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from backend.models.provider import ProviderHealth, ProviderInfo
from backend.models.tool import ToolDefinition, ToolExecutionResult


class BaseProviderAdapter(ABC):
    @property
    @abstractmethod
    def provider_info(self) -> ProviderInfo:
        """Return provider metadata and health."""
        pass

    @abstractmethod
    def discover_tools(self) -> List[ToolDefinition]:
        """Discover and return all tool definitions exposed by this provider."""
        pass

    @abstractmethod
    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> ToolExecutionResult:
        """Execute a specific provider tool with validated arguments."""
        pass

    @abstractmethod
    def get_health(self) -> ProviderHealth:
        """Return live health state."""
        pass
