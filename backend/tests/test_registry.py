"""Unit tests for Dynamic Tool Registry and Capability Mapping."""
import unittest
from backend.models.tool import ToolClassification, ToolDefinition, ToolStatus
from backend.registry.capability_map import CanonicalCapability
from backend.registry.tool_registry import ToolRegistry


class TestToolRegistry(unittest.TestCase):
    def setUp(self):
        self.registry = ToolRegistry()

    def test_register_and_find_tools_by_capability(self):
        tool1 = ToolDefinition(
            tool_id="alpha_search",
            provider_id="provider_alpha",
            tool_name="search_products",
            description="Search products",
            input_schema={"type": "object"},
            canonical_capability=CanonicalCapability.PRODUCT_SEARCH,
            classification=ToolClassification.READ_ONLY
        )
        tool2 = ToolDefinition(
            tool_id="beta_search",
            provider_id="provider_beta",
            tool_name="find_items",
            description="Find items",
            input_schema={"type": "object"},
            canonical_capability=CanonicalCapability.PRODUCT_SEARCH,
            classification=ToolClassification.READ_ONLY
        )

        self.registry.register_tool(tool1)
        self.registry.register_tool(tool2)

        matches = self.registry.find_tools_by_capability(CanonicalCapability.PRODUCT_SEARCH)
        self.assertEqual(len(matches), 2)
        tool_ids = {t.tool_id for t in matches}
        self.assertIn("alpha_search", tool_ids)
        self.assertIn("beta_search", tool_ids)

    def test_reject_unknown_capability(self):
        invalid_tool = ToolDefinition(
            tool_id="bad_tool",
            provider_id="provider_test",
            tool_name="do_something_random",
            description="Invalid capability",
            input_schema={},
            canonical_capability="NON_EXISTENT_CAPABILITY"
        )
        with self.assertRaises(ValueError):
            self.registry.register_tool(invalid_tool)

    def test_provider_status_invalidation(self):
        tool = ToolDefinition(
            tool_id="alpha_cart",
            provider_id="provider_alpha",
            tool_name="add_to_cart",
            description="Add to cart",
            input_schema={"type": "object"},
            canonical_capability=CanonicalCapability.CART_ADD,
            classification=ToolClassification.REVERSIBLE_STATE_CHANGE
        )
        self.registry.register_tool(tool)

        # Before invalidation
        active_tools = self.registry.find_tools_by_capability(CanonicalCapability.CART_ADD, active_only=True)
        self.assertEqual(len(active_tools), 1)

        # Invalidate provider
        self.registry.mark_provider_tools_status("provider_alpha", ToolStatus.UNAVAILABLE)

        active_tools_after = self.registry.find_tools_by_capability(CanonicalCapability.CART_ADD, active_only=True)
        self.assertEqual(len(active_tools_after), 0)

        # All tools still returned when active_only=False
        all_tools = self.registry.find_tools_by_capability(CanonicalCapability.CART_ADD, active_only=False)
        self.assertEqual(len(all_tools), 1)
        self.assertEqual(all_tools[0].status, ToolStatus.UNAVAILABLE)


if __name__ == "__main__":
    unittest.main()
