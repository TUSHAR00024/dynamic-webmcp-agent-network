"""Provider metadata, capability registration, and health models."""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ProviderType(str, Enum):
    WEBMCP_SITE = "webmcp_site"
    REMOTE_MCP = "remote_mcp"
    INTERNAL_DEMO = "internal_demo"


class ProviderHealth(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNREACHABLE = "unreachable"


@dataclass
class ProviderInfo:
    provider_id: str
    name: str
    description: str
    provider_type: ProviderType
    origin_url: str
    supported_capabilities: List[str] = field(default_factory=list)
    health: ProviderHealth = ProviderHealth.HEALTHY
    data_quality_score: float = 0.90  # 0.0 - 1.0 based on specification completeness
    historical_reliability: float = 0.95  # 0.0 - 1.0 success rate
    average_latency_ms: float = 120.0
    estimated_cost_per_query: float = 0.0
    last_discovered_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["provider_type"] = self.provider_type.value if isinstance(self.provider_type, ProviderType) else self.provider_type
        d["health"] = self.health.value if isinstance(self.health, ProviderHealth) else self.health
        return d


@dataclass
class ProviderScoreBreakdown:
    provider_id: str
    capability_match_score: float
    data_quality_score: float
    reliability_score: float
    freshness_score: float
    latency_penalty: float
    cost_penalty: float
    composite_score: float
    selection_rationale: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
