"""Unit tests for Parallel Provider Search and Fallback Recovery."""
import unittest
from backend.models.product import ProductRecord
from backend.registry.capability_map import CanonicalCapability
from backend.routing.tool_router import tool_router


class TestParallelSearchAndFallback(unittest.TestCase):
    def test_parallel_search_queries_multiple_providers_and_merges(self):
        # Search for laptops with max budget of ₹70,000
        canonical_query = {
            "query": "laptop",
            "max_price": 70000.0
        }

        products, decisions = tool_router.route_parallel_search(canonical_query)

        # Must find items from both Provider Alpha and Provider Beta
        self.assertGreaterEqual(len(products), 3, "Expected at least 3 qualifying laptop options under ₹70,000")
        self.assertGreaterEqual(len(decisions), 2, "Expected routing decisions for both Alpha and Beta")

        providers_found = {p.provider_id for p in products}
        self.assertIn("provider_alpha", providers_found, "Expected laptops from Provider Alpha")
        self.assertIn("provider_beta", providers_found, "Expected laptops from Provider Beta")

        # Verify all products adhere to hard budget constraint
        for p in products:
            self.assertLessEqual(p.price, 70000.0, f"Product {p.title} at ₹{p.price} violates ₹70,000 budget constraint!")
            self.assertIsInstance(p, ProductRecord)

    def test_automatic_fallback_recovery_when_provider_fails(self):
        # Explicitly request Provider Gamma (configured to fail with simulated 503 error)
        res, decision = tool_router.route_and_execute(
            canonical_capability=CanonicalCapability.PRODUCT_SEARCH,
            canonical_args={"query": "laptop", "max_price": 70000.0},
            preferred_provider_id="provider_gamma",
            enable_fallback=True
        )

        # Fallback manager should have intercepted the failure and recovered via Alpha or Beta
        self.assertEqual(res.status, "SUCCESS", "Expected successful recovery via fallback provider")
        self.assertIn("Recovered via fallback", decision.rationale)
        self.assertNotEqual(decision.selected_provider_id, "provider_gamma")
        self.assertIn(decision.selected_provider_id, ["provider_alpha", "provider_beta"])

    def test_cart_operation_routed_to_specific_provider(self):
        # Add item to Alpha's cart
        res, dec = tool_router.route_and_execute(
            canonical_capability=CanonicalCapability.CART_ADD,
            canonical_args={
                "session_id": "test_session_42",
                "product_id": "alpha_thinkpad_e14",
                "quantity": 1
            },
            preferred_provider_id="provider_alpha"
        )
        self.assertEqual(res.status, "VERIFIED")
        self.assertEqual(dec.selected_provider_id, "provider_alpha")

        # Read back cart state from Alpha
        cart_res, cart_dec = tool_router.route_and_execute(
            canonical_capability=CanonicalCapability.CART_READ,
            canonical_args={"session_id": "test_session_42"},
            preferred_provider_id="provider_alpha"
        )
        self.assertEqual(cart_res.status, "SUCCESS")
        items = cart_res.payload.get("items", [])
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["product_id"], "alpha_thinkpad_e14")
        self.assertEqual(items[0]["quantity"], 1)


if __name__ == "__main__":
    unittest.main()
