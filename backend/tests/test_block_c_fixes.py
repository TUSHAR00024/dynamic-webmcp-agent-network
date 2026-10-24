"""Regression tests for BLOCK C fixes: Reliability, truthful scoring, and grounded fallback."""
import unittest

from backend.llm.asi1_client import asi1_client
from backend.models.product import ProductRecord, ProductSpecs
from backend.registry.capability_map import CanonicalCapability
from backend.registry.tool_registry import tool_registry
from backend.routing.candidate_scorer import (
    parse_numeric_cpu_cores,
    parse_numeric_ram_gb,
    parse_numeric_battery_wh,
    score_candidate
)
from backend.services.workflow_service import workflow_service


class TestBlockCFixes(unittest.TestCase):

    # -------------------------------------------------------------
    # C2: Priority weighting changes the winner
    # -------------------------------------------------------------
    def test_c2_priority_weighting_changes_winner(self):
        """Dynamic priority weights must legitimately shift the winning product between coding and battery priorities."""
        prod_coding_champ = ProductRecord(
            product_id="prod_coding",
            provider_id="provider_alpha",
            sku="sku_coding",
            title="DevPro CodeMaster 16",
            brand="DevPro",
            price=68000.0,
            specs=ProductSpecs(
                cpu="AMD Ryzen 9 7940HS (16 cores, 32 threads)",
                ram="32GB DDR5 5600MHz",
                battery="52Wh (estimated 5 hours)",
                warranty="1-year onsite"
            ),
            rating=4.8
        )

        prod_battery_champ = ProductRecord(
            product_id="prod_battery",
            provider_id="provider_beta",
            sku="sku_battery",
            title="EnduranceAir All-Day",
            brand="Endurance",
            price=64000.0,
            specs=ProductSpecs(
                cpu="Intel Core i3-1215U (4 cores)",
                ram="8GB LPDDR4X",
                battery="80Wh (estimated 16 hours)",
                warranty="1-year standard"
            ),
            rating=4.5
        )

        # 1. When user prioritizes coding performance
        score_coding_for_coder = score_candidate(prod_coding_champ, budget=70000.0, priorities=["coding"])
        score_battery_for_coder = score_candidate(prod_battery_champ, budget=70000.0, priorities=["coding"])
        self.assertGreater(
            score_coding_for_coder,
            score_battery_for_coder,
            f"CodeMaster ({score_coding_for_coder}) should outrank EnduranceAir ({score_battery_for_coder}) when coding is prioritized"
        )

        # 2. When user prioritizes battery endurance
        score_coding_for_battery = score_candidate(prod_coding_champ, budget=70000.0, priorities=["battery"])
        score_battery_for_battery = score_candidate(prod_battery_champ, budget=70000.0, priorities=["battery"])
        self.assertGreater(
            score_battery_for_battery,
            score_coding_for_battery,
            f"EnduranceAir ({score_battery_for_battery}) should outrank CodeMaster ({score_coding_for_battery}) when battery is prioritized"
        )

    def test_c2_cart_tool_capability_lookup(self):
        """Target cart tool must be resolved via capability lookup in tool_registry, not provider-id string."""
        tools_alpha = tool_registry.find_tools(CanonicalCapability.CART_ADD, provider_id="provider_alpha")
        self.assertTrue(len(tools_alpha) >= 1)
        self.assertEqual(tools_alpha[0].tool_name, "add_to_cart")

        tools_beta = tool_registry.find_tools(CanonicalCapability.CART_ADD, provider_id="provider_beta")
        self.assertTrue(len(tools_beta) >= 1)
        self.assertEqual(tools_beta[0].tool_name, "cart_add")

    # -------------------------------------------------------------
    # C3: Grounded fallback rationale
    # -------------------------------------------------------------
    def test_c3_templated_fallback_truthfulness_unknown_battery(self):
        """Fallback rationale must state battery is unknown/unverified if candidate spec is unknown."""
        candidate = {
            "title": "Budget Slim 14",
            "price": 45000.0,
            "provider_id": "provider_alpha",
            "specs": {
                "cpu": "Intel Core i5",
                "ram": "8GB",
                "battery": "unknown",
                "warranty": "1-year"
            }
        }
        rationale = asi1_client.generate_comparison_rationale([candidate], candidate, ["coding"])
        self.assertIn("unknown", rationale.lower(), "Rationale must explicitly mention unknown battery")
        self.assertNotIn("verified battery capacity", rationale.lower(), "Must NOT falsely claim verified battery capacity")

    def test_c3_templated_fallback_truthfulness_real_specs(self):
        """Fallback rationale must reflect actual battery capacity when present."""
        candidate = {
            "title": "ZenBook OLED",
            "price": 65000.0,
            "provider_id": "provider_alpha",
            "specs": {
                "cpu": "AMD Ryzen 7",
                "ram": "16GB",
                "battery": "75Wh",
                "warranty": "2-year"
            }
        }
        rationale = asi1_client.generate_comparison_rationale([candidate], candidate, ["battery"])
        self.assertIn("75wh", rationale.lower())
        self.assertIn("2-year", rationale.lower())


if __name__ == "__main__":
    unittest.main()
