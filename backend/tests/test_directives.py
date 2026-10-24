"""Tests verifying the 6 Core Operational Directives for ASI:One & Agentverse."""
import asyncio
import json
import unittest
from unittest.mock import MagicMock

from backend.routing.candidate_scorer import sanitize_user_query
from backend.bridge.candidate_scorer import sanitize_user_query as bridge_sanitize
from backend.uagent_app import process_user_text, _orders
from scripts.agentverse_hosted_agent import (
    sanitize_user_query as hosted_sanitize,
    is_greeting as hosted_is_greeting,
    parse_structured_form as hosted_parse_form,
    search_all_sources as hosted_search,
    score_candidate as hosted_score,
    WELCOME_GUIDE
)


class TestCoreDirectives(unittest.TestCase):
    def test_directive_1_handle_stripping(self):
        """Directive 1: Platform tags and handles (@webmcp, webmcp:) must be cleanly stripped."""
        self.assertEqual(sanitize_user_query("@webmcp chairs"), "chairs")
        self.assertEqual(sanitize_user_query("webmcp: chairs"), "chairs")
        self.assertEqual(sanitize_user_query("@agent find laptops under 70000"), "find laptops under 70000")
        self.assertEqual(sanitize_user_query("@webmcp"), "general products")
        self.assertEqual(bridge_sanitize("@webmcp chairs"), "chairs")
        self.assertEqual(hosted_sanitize("@webmcp chairs"), "chairs")

    def test_directive_2_greeting_intent(self):
        """Directive 2: Initial greetings must return welcome guide without running product search."""
        for greeting in ["hi", "hello", "hey", "start", "help", "@webmcp hi", "hello there"]:
            clean = sanitize_user_query(greeting)
            self.assertTrue(hosted_is_greeting(clean), f"Failed for {greeting}")

            # Verify in uagent_app
            ctx = MagicMock()
            reply = asyncio.run(process_user_text(ctx, "agent1_test_user", greeting))
            text = reply.text()
            self.assertIn("Welcome to Dynamic WebMCP Shopping Agent!", text)
            self.assertNotIn("🎯 **Product Comparison", text)

    def test_directive_3_and_4_search_and_ranking_chairs(self):
        """Directives 3 & 4: Search for chairs under 15000 must find items and recommend ErgoSmart Pro."""
        candidates = asyncio.run(hosted_search("chairs", max_price=15000.0))
        self.assertTrue(len(candidates) >= 1)
        ranked = sorted(candidates, key=lambda c: hosted_score(c, 15000.0), reverse=True)
        top = ranked[0]
        self.assertEqual(top["title"], "ErgoSmart Pro Office Chair")
        self.assertEqual(top["price"], 12499.0)

    def test_directive_5_parameter_collection_template(self):
        """Directive 5: Missing parameters (like budget) must render the Product Finder Setup template."""
        ctx = MagicMock()
        reply = asyncio.run(process_user_text(ctx, "agent1_test_user", "chairs"))
        text = reply.text()
        self.assertIn("📋 **Product Finder Setup:**", text)
        self.assertIn("Maximum Budget:", text)

        # Also test structured form parser
        form_text = (
            "📋 Product Finder Setup:\n"
            "- Target Product: Ergonomic Chair\n"
            "- Maximum Budget: 15000\n"
            "- Priority Feature: Lumbar support"
        )
        parsed = hosted_parse_form(form_text)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["product"], "Ergonomic Chair")
        self.assertEqual(parsed["budget"], 15000.0)
        self.assertEqual(parsed["feature"], "Lumbar support")

    def test_directive_6_payment_protocol_flow(self):
        """Directive 6: Approval must trigger Fetch.ai Payment Protocol and confirm on CONFIRM_PAYMENT."""
        ctx = MagicMock()
        # 1. Search for a product
        reply = asyncio.run(process_user_text(ctx, "agent1_test_buyer", "Find a laptop under 70000 and add to cart"))
        text = reply.text()
        import re
        m = re.search(r"APPROVE\s+(appr_[0-9a-zA-Z_]+)", text)
        self.assertIsNotNone(m)
        token = m.group(1)

        # 2. Approve item -> Expect Payment Authorization Request
        reply_appr = asyncio.run(process_user_text(ctx, "agent1_test_buyer", f"APPROVE {token}"))
        appr_text = reply_appr.text()
        self.assertIn("Action Authorized and Verified!", appr_text)
        self.assertIn("Fetch.ai Payment Protocol Authorization Request", appr_text)
        self.assertIn("Merchant / Provider Address:", appr_text)
        self.assertIn("Fetch.ai Dorado Testnet", appr_text)

        ord_m = re.search(r"CONFIRM_PAYMENT\s+(ord_[0-9a-zA-Z_]+)", appr_text)
        self.assertIsNotNone(ord_m)
        order_id = ord_m.group(1)

        # 3. Confirm payment -> Expect final on-chain settlement receipt
        reply_settle = asyncio.run(process_user_text(ctx, "agent1_test_buyer", f"CONFIRM_PAYMENT {order_id}"))
        settle_text = reply_settle.text()
        self.assertIn("Payment Successfully Settled & Verified!", settle_text)
        self.assertIn("Transaction Hash:", settle_text)
        self.assertIn("CONFIRMED_ON_CHAIN", settle_text)


if __name__ == "__main__":
    unittest.main()
