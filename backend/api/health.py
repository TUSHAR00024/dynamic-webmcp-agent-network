"""Health and catalog introspection API."""
from typing import Any, Dict, List
from backend.registry.provider_registry import provider_registry
from backend.registry.tool_registry import tool_registry
from backend.routing.tool_router import tool_router


class HealthAPI:
    @staticmethod
    def handle_health() -> Dict[str, Any]:
        providers = provider_registry.list_providers()
        tools = tool_registry.list_all_tools()
        return {
            "status": "HEALTHY",
            "system": "Dynamic WebMCP Agent Network",
            "version": "1.0.0",
            "active_providers_count": len(providers),
            "registered_tools_count": len(tools),
            "providers": [p.to_dict() for p in providers]
        }

    @staticmethod
    def handle_tools() -> Dict[str, Any]:
        tools = tool_registry.list_all_tools()
        return {"tools": [t.to_dict() for t in tools], "count": len(tools)}

    @staticmethod
    def handle_products() -> Dict[str, Any]:
        # Return merged list of products across providers
        prods, _ = tool_router.route_parallel_search({"query": ""})
        return {"products": [p.to_dict() for p in prods], "count": len(prods)}
