"""Routing policy and constraint filtering."""
from typing import Dict, List, Tuple
from backend.models.provider import ProviderHealth, ProviderInfo
from backend.models.tool import ToolClassification, ToolDefinition


class RoutingPolicy:
    @staticmethod
    def filter_eligible_providers(
        providers: List[ProviderInfo],
        tools: List[ToolDefinition],
        required_capability: str,
        allow_degraded: bool = False
    ) -> Tuple[List[ProviderInfo], Dict[str, str]]:
        """Filter out providers that cannot fulfill the capability or violate constraints."""
        eligible: List[ProviderInfo] = []
        excluded: Dict[str, str] = {}

        # Build mapping of provider_id -> available tools
        provider_tools_map: Dict[str, List[ToolDefinition]] = {}
        for t in tools:
            provider_tools_map.setdefault(t.provider_id, []).append(t)

        for p in providers:
            # 1. Health check
            if p.health == ProviderHealth.UNREACHABLE:
                excluded[p.provider_id] = "Provider health is UNREACHABLE."
                continue
            if p.health == ProviderHealth.DEGRADED and not allow_degraded:
                excluded[p.provider_id] = "Provider health is DEGRADED and degraded mode is disabled."
                continue

            # 2. Capability check
            if required_capability not in p.supported_capabilities:
                excluded[p.provider_id] = f"Does not advertise capability '{required_capability}'."
                continue

            # 3. Available active tool check
            p_tools = provider_tools_map.get(p.provider_id, [])
            matching_tools = [t for t in p_tools if t.canonical_capability == required_capability]
            if not matching_tools:
                excluded[p.provider_id] = f"No active registered tool found for '{required_capability}'."
                continue

            eligible.append(p)

        return eligible, excluded
