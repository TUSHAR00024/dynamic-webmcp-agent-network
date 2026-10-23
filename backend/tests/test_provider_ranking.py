"""Unit tests for Provider Ranking and Policy Filtering."""
import unittest
from backend.models.provider import ProviderHealth, ProviderInfo, ProviderType
from backend.models.tool import ToolClassification, ToolDefinition
from backend.registry.capability_map import CanonicalCapability
from backend.routing.provider_ranker import ProviderRanker
from backend.routing.routing_policy import RoutingPolicy


class TestProviderRanking(unittest.TestCase):
    def setUp(self):
        self.ranker = ProviderRanker()

        self.alpha = ProviderInfo(
            provider_id="provider_alpha",
            name="Alpha",
            description="",
            provider_type=ProviderType.WEBMCP_SITE,
            origin_url="",
            supported_capabilities=[CanonicalCapability.PRODUCT_SEARCH, CanonicalCapability.CART_ADD],
            health=ProviderHealth.HEALTHY,
            data_quality_score=0.95,
            historical_reliability=0.98,
            average_latency_ms=80.0
        )

        self.beta = ProviderInfo(
            provider_id="provider_beta",
            name="Beta",
            description="",
            provider_type=ProviderType.REMOTE_MCP,
            origin_url="",
            supported_capabilities=[CanonicalCapability.PRODUCT_SEARCH, CanonicalCapability.CART_ADD],
            health=ProviderHealth.HEALTHY,
            data_quality_score=0.80,
            historical_reliability=0.85,
            average_latency_ms=250.0
        )

        self.gamma_unreachable = ProviderInfo(
            provider_id="provider_gamma",
            name="Gamma",
            description="",
            provider_type=ProviderType.REMOTE_MCP,
            origin_url="",
            supported_capabilities=[CanonicalCapability.PRODUCT_SEARCH],
            health=ProviderHealth.UNREACHABLE,
            data_quality_score=0.50,
            historical_reliability=0.30,
            average_latency_ms=900.0
        )

    def test_ranking_orders_by_quality_and_reliability(self):
        scores = self.ranker.rank_providers([self.beta, self.alpha], CanonicalCapability.PRODUCT_SEARCH)
        self.assertEqual(len(scores), 2)
        # Alpha has higher quality (0.95 vs 0.80) and reliability (0.98 vs 0.85) and lower latency
        self.assertEqual(scores[0].provider_id, "provider_alpha")
        self.assertEqual(scores[1].provider_id, "provider_beta")
        self.assertGreater(scores[0].composite_score, scores[1].composite_score)

    def test_policy_filters_unreachable_providers(self):
        tools = [
            ToolDefinition(
                tool_id="t1", provider_id="provider_alpha", tool_name="search",
                description="", input_schema={}, canonical_capability=CanonicalCapability.PRODUCT_SEARCH
            ),
            ToolDefinition(
                tool_id="t2", provider_id="provider_gamma", tool_name="search",
                description="", input_schema={}, canonical_capability=CanonicalCapability.PRODUCT_SEARCH
            )
        ]

        eligible, excluded = RoutingPolicy.filter_eligible_providers(
            [self.alpha, self.gamma_unreachable],
            tools,
            CanonicalCapability.PRODUCT_SEARCH
        )
        self.assertEqual(len(eligible), 1)
        self.assertEqual(eligible[0].provider_id, "provider_alpha")
        self.assertIn("provider_gamma", excluded)
        self.assertIn("UNREACHABLE", excluded["provider_gamma"])


if __name__ == "__main__":
    unittest.main()
