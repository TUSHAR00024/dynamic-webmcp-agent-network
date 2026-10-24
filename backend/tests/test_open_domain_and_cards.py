"""Tests for Generalized Tool Routing, Open-Domain Coverage, and Interactive Cards."""
import json
import os
import unittest
from pathlib import Path

from backend.adapters.demo_provider_adapter import ProviderAlphaAdapter, ProviderBetaAdapter
from backend.cards import (
    build_approval_review_card,
    build_product_carousel_card,
    create_carousel_metadata,
    create_review_metadata,
)
from backend.llm.asi1_client import asi1_client
from backend.models.product import ProductRecord, ProductSpecs
from backend.registry.schema_normalizer import SchemaNormalizer
from backend.routing.candidate_scorer import score_candidate
from backend.routing.tool_router import tool_router
from backend.safety.approvals import (
    ApprovalTokenStore,
    compute_hmac_signature,
    verify_hmac_signature,
)
from backend.services.workflow_service import workflow_service


class TestOpenDomainAndCards(unittest.TestCase):

    def test_open_domain_monitors_search_and_normalization(self):
        """User requesting computer monitors must discover monitors dynamically across providers."""
        plan = asi1_client.extract_intent_and_constraints("Find a 4K computer monitor under 60000 with good refresh rate")
        self.assertEqual(plan.category, "monitors")
        self.assertEqual(plan.query, "monitor")
        self.assertEqual(plan.max_budget, 60000.0)

        products, decisions = tool_router.route_parallel_search({"query": plan.query, "max_price": plan.max_budget})
        self.assertGreaterEqual(len(products), 2, "Expected at least 2 monitors under 60k")

        # Verify dynamic normalization preserved monitor specs
        titles = [p.title for p in products]
        self.assertTrue(any("UltraSharp" in t or "Dell" in t for t in titles))
        self.assertTrue(any("Samsung" in t or "BenQ" in t or "LG" in t for t in titles))

        for p in products:
            self.assertIsInstance(p.specs, ProductSpecs)
            # Specs must not throw error on category-specific keys
            self.assertIsNotNone(p.specs.get("refresh_rate") or p.specs.get("resolution") or p.specs.display)

    def test_open_domain_office_furniture_search(self):
        """User requesting office chairs must discover ergonomic furniture dynamically."""
        plan = asi1_client.extract_intent_and_constraints("Find ergonomic office furniture chair under 40000")
        self.assertEqual(plan.category, "furniture")
        self.assertEqual(plan.query, "office chair")
        self.assertEqual(plan.max_budget, 40000.0)

        products, _ = tool_router.route_parallel_search({"query": plan.query, "max_price": plan.max_budget})
        self.assertGreaterEqual(len(products), 2, "Expected at least 2 chairs under 40k")

        titles = [p.title for p in products]
        self.assertTrue(any("Helix" in t or "Featherlite" in t for t in titles))
        self.assertTrue(any("Steelcase" in t for t in titles))

    def test_open_domain_cloud_and_software_search(self):
        """User requesting cloud compute or software subscription must discover services."""
        plan = asi1_client.extract_intent_and_constraints("Find cloud compute services under 50000")
        self.assertEqual(plan.category, "cloud_services")
        self.assertEqual(plan.query, "cloud compute")

        products, _ = tool_router.route_parallel_search({"query": plan.query, "max_price": 50000.0})
        self.assertGreaterEqual(len(products), 1, "Expected at least 1 cloud compute package")
        self.assertTrue(any("AWS" in p.title for p in products))

    def test_candidate_scorer_adapts_to_monitors_and_priorities(self):
        """Scorer must adapt to monitors and shift weight when gaming/refresh rate is prioritized."""
        alpha = ProviderAlphaAdapter()
        lg_raw = alpha._products["alpha_lg_27gr75q"]
        lg_prod = SchemaNormalizer.normalize_product_record("provider_alpha", lg_raw)

        dell_raw = alpha._products["alpha_dell_u2723qe"]
        dell_prod = SchemaNormalizer.normalize_product_record("provider_alpha", dell_raw)

        # LG has 165Hz gaming refresh rate; Dell has 60Hz 4K designer
        gaming_score_lg = score_candidate(lg_prod, budget=60000.0, priorities=["gaming", "refresh"])
        gaming_score_dell = score_candidate(dell_prod, budget=60000.0, priorities=["gaming", "refresh"])
        self.assertGreater(gaming_score_lg, gaming_score_dell, "Gaming monitor with 165Hz should outscore 60Hz on gaming priority")

        designer_score_dell = score_candidate(dell_prod, budget=60000.0, priorities=["designer", "4k"])
        designer_score_lg = score_candidate(lg_prod, budget=60000.0, priorities=["designer", "4k"])
        self.assertGreater(designer_score_dell, designer_score_lg, "4K monitor should outscore QHD on designer priority")

    def test_schema_normalizer_never_throws_on_arbitrary_category_keys(self):
        """Normalizer must handle arbitrary category keys without raising validation errors."""
        raw_custom = {
            "id": "custom_hotel_suite",
            "name": "Luxury Skyline Suite",
            "category": "travel",
            "price": 15000.0,
            "specs": {
                "check_in": "14:00",
                "room_type": "Presidential Suite",
                "amenities": ["WiFi", "Pool", "Breakfast"],
                "cancellation": "Free up to 24h"
            }
        }
        record = SchemaNormalizer.normalize_product_record("provider_alpha", raw_custom)
        self.assertEqual(record.title, "Luxury Skyline Suite")
        self.assertEqual(record.specs.get("room_type"), "Presidential Suite")
        self.assertEqual(record.specs.category, "travel")
        # to_dict must flatten custom attributes
        d = record.to_dict()
        self.assertEqual(d["specs"]["room_type"], "Presidential Suite")

    def test_asi1_interactive_card_metadata_compliance(self):
        """Interactive cards must produce Agentverse-compliant MetadataContent with JSON payloads."""
        candidates = [
            {"product_id": "m1", "title": "Dell 4K", "price": 54990, "provider_id": "provider_alpha", "specs": {"resolution": "4K", "refresh_rate": "60Hz"}},
            {"product_id": "m2", "title": "LG 165Hz", "price": 24990, "provider_id": "provider_alpha", "specs": {"refresh_rate": "165Hz"}}
        ]
        carousel_meta = create_carousel_metadata(candidates, candidates[0])
        self.assertEqual(carousel_meta.type, "metadata")
        self.assertEqual(carousel_meta.metadata["card_protocol_version"], "1")
        self.assertEqual(carousel_meta.metadata["requires_card_interaction"], "true")
        self.assertEqual(carousel_meta.metadata["card_kind"], "carousel")

        # Must parse as valid JSON
        payload = json.loads(carousel_meta.metadata["card_payload"])
        self.assertEqual(len(payload["items"]), 2)
        self.assertEqual(payload["items"][0]["badges"], ["⭐ Top Pick"])

    def test_hmac_approvals_token_generation_and_tamper_defense(self):
        """HMAC signatures generated via approvals.py must defend against tampering."""
        task_id = "task_test_99"
        provider_id = "provider_alpha"
        target_tool = "add_to_cart"
        args = {"session_id": "sess_1", "product_id": "alpha_dell_u2723qe", "quantity": 1}
        price = 54990.0

        sig = compute_hmac_signature(task_id, provider_id, target_tool, args, price)
        self.assertTrue(verify_hmac_signature(sig, task_id, provider_id, target_tool, args, price))

        # Tampered argument must be rejected
        tampered_args = {"session_id": "sess_1", "product_id": "alpha_dell_u2723qe", "quantity": 99}
        self.assertFalse(verify_hmac_signature(sig, task_id, provider_id, target_tool, tampered_args, price))

        # Tampered price must be rejected
        self.assertFalse(verify_hmac_signature(sig, task_id, provider_id, target_tool, args, 1.0))

    def test_approval_store_lifecycle_and_sender_binding(self):
        """ApprovalTokenStore must enforce TTL, consumption, and sender address binding."""
        store = ApprovalTokenStore()
        record = store.issue_token(
            task_id="t1",
            provider_id="provider_alpha",
            target_tool="add_to_cart",
            arguments={"item": "desk"},
            bound_price=10000.0,
            sender_address="agent1q_owner"
        )
        appr_id = record["approval_id"]

        # Unauthorized sender attempt
        valid, msg, _ = store.validate_and_consume(appr_id, current_price=10000.0, sender_address="agent1q_attacker")
        self.assertFalse(valid)
        self.assertIn("does not match bound requester", msg)

        # Authorized sender attempt
        valid, msg, consumed = store.validate_and_consume(appr_id, current_price=10000.0, sender_address="agent1q_owner")
        self.assertTrue(valid)
        self.assertEqual(consumed["status"], "CONSUMED")

        # Double consumption (replay) attempt
        valid2, msg2, _ = store.validate_and_consume(appr_id, current_price=10000.0, sender_address="agent1q_owner")
        self.assertFalse(valid2)
        self.assertIn("already CONSUMED", msg2)


if __name__ == "__main__":
    unittest.main()
