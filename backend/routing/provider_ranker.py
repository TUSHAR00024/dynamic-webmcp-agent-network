"""Provider Ranking and Multi-Factor Scoring Engine."""
import logging
from typing import Dict, List, Optional
from backend.models.provider import ProviderInfo, ProviderScoreBreakdown

logger = logging.getLogger("Routing.ProviderRanker")


class ProviderRanker:
    """Ranks eligible providers using normalized weights."""

    def __init__(
        self,
        weight_match: float = 0.35,
        weight_quality: float = 0.25,
        weight_reliability: float = 0.20,
        weight_freshness: float = 0.10,
        weight_latency: float = 0.10,
        weight_cost: float = 0.0
    ):
        self.w_match = weight_match
        self.w_quality = weight_quality
        self.w_reliability = weight_reliability
        self.w_freshness = weight_freshness
        self.w_latency = weight_latency
        self.w_cost = weight_cost

    def score_provider(
        self,
        provider: ProviderInfo,
        requested_capability: str
    ) -> ProviderScoreBreakdown:
        """Compute composite score for a provider executing a capability."""

        # 1. Capability match score (1.0 if explicitly supported, 0.0 otherwise)
        has_cap = requested_capability in provider.supported_capabilities
        s_match = 1.0 if has_cap else 0.0

        # 2. Data quality score (0.0 to 1.0)
        s_quality = max(0.0, min(1.0, provider.data_quality_score))

        # 3. Reliability score (0.0 to 1.0)
        s_rel = max(0.0, min(1.0, provider.historical_reliability))

        # 4. Freshness score (1.0 default for active registered sessions)
        s_fresh = 1.0

        # 5. Latency penalty (normalized: 0 ms -> 0.0 penalty, 1000 ms -> 1.0 penalty)
        p_latency = min(1.0, provider.average_latency_ms / 1000.0)

        # 6. Cost penalty
        p_cost = min(1.0, provider.estimated_cost_per_query / 10.0)

        composite = (
            (self.w_match * s_match) +
            (self.w_quality * s_quality) +
            (self.w_reliability * s_rel) +
            (self.w_freshness * s_fresh) -
            (self.w_latency * p_latency) -
            (self.w_cost * p_cost)
        )
        composite = round(max(0.0, min(1.0, composite)), 4)

        rationale = (
            f"Composite: {composite:.4f} (Quality: {s_quality:.2f}, Reliability: {s_rel:.2f}, "
            f"Latency: {provider.average_latency_ms:.0f}ms)"
        )

        return ProviderScoreBreakdown(
            provider_id=provider.provider_id,
            capability_match_score=s_match,
            data_quality_score=s_quality,
            reliability_score=s_rel,
            freshness_score=s_fresh,
            latency_penalty=p_latency,
            cost_penalty=p_cost,
            composite_score=composite,
            selection_rationale=rationale
        )

    def rank_providers(
        self,
        providers: List[ProviderInfo],
        requested_capability: str
    ) -> List[ProviderScoreBreakdown]:
        """Rank candidate providers in descending order of composite score."""
        scores = [self.score_provider(p, requested_capability) for p in providers]
        scores.sort(key=lambda s: s.composite_score, reverse=True)
        return scores


provider_ranker = ProviderRanker()
