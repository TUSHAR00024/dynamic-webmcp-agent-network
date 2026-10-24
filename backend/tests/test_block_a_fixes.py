"""Regression tests for BLOCK A fixes (Round 2 corrections)."""
import json
import os
import unittest
from unittest.mock import patch, MagicMock

from backend.llm.asi1_client import asi1_client, ExtractedPlan, sanitize_budget_value
from backend.cards import (
    build_approval_review_card,
    build_product_carousel_card,
    create_card_metadata,
    create_carousel_metadata,
    create_review_metadata
)
from backend.models.product import ProductRecord, ProductSpecs
from backend.models.tool import ToolExecutionResult
from backend.services.workflow_service import workflow_service
from backend.agents.policy_agent import policy_agent
from backend.safety.idempotency import idempotency_guard
from backend.uagent_app import process_user_text, make_chat_msg


class TestBlockAFixes(unittest.TestCase):

    # -------------------------------------------------------------
    # A1: Lazy ASI1 client activation
    # -------------------------------------------------------------
    def test_a1_lazy_client_activation_on_env_var(self):
        """Setting ASI1_API_KEY dynamically must activate the client lazily."""
        old_key = os.environ.get("ASI1_API_KEY")
        try:
            # When unset
            os.environ["ASI1_API_KEY"] = ""
            asi1_client._ensure_client()
            self.assertIsNone(asi1_client.client)

            # When set
            os.environ["ASI1_API_KEY"] = "sk-fake-test-key-for-activation"
            asi1_client._ensure_client()
            self.assertIsNotNone(asi1_client.client)
        finally:
            if old_key is not None:
                os.environ["ASI1_API_KEY"] = old_key
            else:
                os.environ.pop("ASI1_API_KEY", None)
            asi1_client._ensure_client()

    # -------------------------------------------------------------
    # A2: Interactive Card Schemas and Response Handling
    # -------------------------------------------------------------
    def test_a2_card_metadata_keys_conform_to_agentverse_spec(self):
        """MetadataContent.metadata must contain exact keys and omit mime_type."""
        candidates = [
            {
                "product_id": "test_p1",
                "title": "ZenBook 14 Pro",
                "price": 65000.0,
                "provider_id": "provider_alpha",
                "specs": {"cpu": "Core i7", "ram": "16GB", "battery": "70Wh"}
            }
        ]
        carousel_meta = create_carousel_metadata(candidates, candidates[0])
        meta = carousel_meta.metadata

        # Exact required keys
        self.assertEqual(meta.get("card_protocol_version"), "1")
        self.assertEqual(meta.get("requires_card_interaction"), "true")
        self.assertEqual(meta.get("card_kind"), "carousel")
        self.assertIn("card_payload", meta)
        self.assertNotIn("mime_type", meta)

        payload = json.loads(meta["card_payload"])
        self.assertEqual(payload["card_kind"], "carousel")
        self.assertEqual(payload["items"][0]["title"], "ZenBook 14 Pro")
        self.assertEqual(payload["items"][0]["primary_cta"]["label"], "Select Option")
        self.assertEqual(payload["items"][0]["primary_cta"]["selection"]["action"], "select_product")

    def test_a2_review_card_schema_and_real_title(self):
        """Review card must carry key-value rows, approve/reject CTAs, and real product title."""
        top_rec = {
            "product_id": "alpha_thinkpad_e14",
            "title": "Lenovo ThinkPad E14 Gen 5",
            "price": 62990.0,
            "provider_id": "provider_alpha"
        }
        approval_req = {
            "approval_id": "appr_test_1234",
            "bound_price": 62990.0,
            "provider_id": "provider_alpha",
            "target_tool": "add_to_cart"
        }
        review_meta = create_review_metadata(approval_req, top_rec)
        meta = review_meta.metadata

        self.assertEqual(meta.get("card_protocol_version"), "1")
        self.assertEqual(meta.get("card_kind"), "review")
        self.assertNotIn("mime_type", meta)

        payload = json.loads(meta["card_payload"])
        self.assertEqual(payload["card_kind"], "review")
        self.assertEqual(payload["rows"][0]["label"], "Product")
        self.assertEqual(payload["rows"][0]["value"], "Lenovo ThinkPad E14 Gen 5")
        self.assertNotEqual(payload["rows"][0]["value"], "Selected Item")

        # CTAs must carry approval_id in selection
        self.assertEqual(payload["approve_cta"]["selection"]["approval_id"], "appr_test_1234")
        self.assertEqual(payload["reject_cta"]["selection"]["approval_id"], "appr_test_1234")

    def test_a2_card_response_handling_json_and_prose(self):
        """Card click JSON selection and prose with approval token must be routed to approval execution."""
        import asyncio
        ctx = MagicMock()
        ctx.logger = MagicMock()

        # 1. Approve via card click JSON
        search_res = workflow_service.run_search_and_compare(
            prompt="Find a laptop under 70000 and add to cart",
            session_id="a2_card_resp_sess"
        )
        approval_id = search_res["approval_request"]["approval_id"]

        card_click_json = json.dumps({"action": "approve", "approval_id": approval_id})
        reply = asyncio.run(process_user_text(ctx, "agent1_user", card_click_json))
        self.assertIn("Action Authorized and Verified!", reply.text())

        # 2. Reject via card click JSON
        search_res_2 = workflow_service.run_search_and_compare(
            prompt="Find a laptop under 70000 and add to cart",
            session_id="a2_card_resp_sess_2"
        )
        approval_id_2 = search_res_2["approval_request"]["approval_id"]
        reject_click_json = json.dumps({"action": "reject", "approval_id": approval_id_2})
        reply_reject = asyncio.run(process_user_text(ctx, "agent1_user", reject_click_json))
        self.assertIn("Action Cancelled", reply_reject.text())

        # 3. Conversational prose containing approval token
        search_res_3 = workflow_service.run_search_and_compare(
            prompt="Find a laptop under 70000 and add to cart",
            session_id="a2_card_resp_sess_3"
        )
        approval_id_3 = search_res_3["approval_request"]["approval_id"]
        reply_prose = asyncio.run(process_user_text(ctx, "agent1_user", f"Yes please confirm and approve {approval_id_3}"))
        self.assertIn("Action Authorized and Verified!", reply_prose.text())

    # -------------------------------------------------------------
    # A3: Truthful verification and failure handling
    # -------------------------------------------------------------
    def test_a3_failed_verification_fails_closed(self):
        """If read-back cart does not contain the item, execute_approved_action must fail closed."""
        search_res = workflow_service.run_search_and_compare(
            prompt="Find a laptop under 70k and add to cart",
            session_id="a3_test_session"
        )
        approval_id = search_res["approval_request"]["approval_id"]

        # Mock cart_agent to return UNVERIFIED postcondition
        from backend.protocols.messages import ActionVerificationResultMessage
        unverified_res = ActionVerificationResultMessage(
            action_id="act_unverified",
            task_id="task_a3",
            status="UNVERIFIED",
            verified_postcondition=False,
            verification_details="Target item missing from cart.",
            cart_state={"items": []}
        )

        with patch("backend.services.workflow_service.cart_agent.execute_and_verify_cart_action", return_value=unverified_res):
            with self.assertRaises(RuntimeError) as ctx:
                workflow_service.execute_approved_action(approval_id)

            self.assertIn("could not be verified", str(ctx.exception))
            # Token must NOT be CONSUMED
            token = policy_agent._tokens[approval_id]
            self.assertEqual(token["status"], "FAILED_VERIFICATION")
            # Must NOT be in idempotency guard
            self.assertIsNone(idempotency_guard.get_existing(approval_id))

    # -------------------------------------------------------------
    # A4: Price re-check fails closed
    # -------------------------------------------------------------
    def test_a4_price_recheck_fails_closed_when_details_fail(self):
        """If live details query fails, execution must abort with PRICE_UNVERIFIABLE and stay PENDING."""
        search_res = workflow_service.run_search_and_compare(
            prompt="Find a laptop under 70000 and add to cart",
            session_id="a4_fail_session"
        )
        approval_id = search_res["approval_request"]["approval_id"]

        failed_res = ToolExecutionResult(
            action_id="act_fail",
            tool_id="tool_details",
            provider_id="provider_alpha",
            tool_name="get_product_details",
            status="FAILED",
            error_message="Gateway timeout"
        )

        with patch("backend.services.workflow_service.tool_router.route_and_execute", return_value=(failed_res, {})):
            with self.assertRaises(ValueError) as ctx:
                workflow_service.execute_approved_action(approval_id)

            self.assertIn("PRICE_UNVERIFIABLE", str(ctx.exception))
            token = policy_agent._tokens[approval_id]
            self.assertEqual(token["status"], "PENDING")

    def test_a4_price_recheck_fails_closed_when_price_missing(self):
        """If returned payload is missing the price key, execution must abort with PRICE_UNVERIFIABLE."""
        search_res = workflow_service.run_search_and_compare(
            prompt="Find a laptop under 70000 and add to cart",
            session_id="a4_missing_session"
        )
        approval_id = search_res["approval_request"]["approval_id"]

        payload_missing_price = ToolExecutionResult(
            action_id="act_missing",
            tool_id="tool_details",
            provider_id="provider_alpha",
            tool_name="get_product_details",
            status="SUCCESS",
            payload={"product": {"title": "Laptop"}}  # No 'price'
        )

        with patch("backend.services.workflow_service.tool_router.route_and_execute", return_value=(payload_missing_price, {})):
            with self.assertRaises(ValueError) as ctx:
                workflow_service.execute_approved_action(approval_id)

            self.assertIn("PRICE_UNVERIFIABLE", str(ctx.exception))
            token = policy_agent._tokens[approval_id]
            self.assertEqual(token["status"], "PENDING")

    # -------------------------------------------------------------
    # A5: Budget parser parametrized regression suite
    # -------------------------------------------------------------
    def test_a5_budget_parser_regression_suite(self):
        """Test edge-cases and word-boundary fixes in deterministic intent extraction."""
        test_cases = [
            ("show me 2 laptops under 50000", 50000.0, 2),
            ("1 laptop under 60k", 60000.0, 1),
            ("Compare 3 laptops under 70,000", 70000.0, 3),
            ("budget of 55000", 55000.0, 1),
            ("laptop under 1.2 lakh", 120000.0, 1),
            ("under 70k", 70000.0, 1),
            ("around ₹65,000 for coding", 65000.0, 1),
            ("laptop under Rs. 45,000", 45000.0, 1),
            ("best laptop for coding", None, 1),
            ("no budget mentioned", None, 1),
        ]

        for prompt, expected_budget, expected_qty in test_cases:
            with self.subTest(prompt=prompt):
                plan = asi1_client._deterministic_extract(prompt)
                self.assertEqual(plan.max_budget, expected_budget, f"Failed budget for '{prompt}'")
                self.assertEqual(plan.quantity, expected_qty, f"Failed quantity for '{prompt}'")

    def test_a5_target_action_word_boundary(self):
        """'additional ram' must not trigger add_to_cart; 'add to cart' must."""
        plan_ram = asi1_client._deterministic_extract("Recommend a laptop with additional ram")
        self.assertIsNone(plan_ram.target_action)

        plan_cart = asi1_client._deterministic_extract("Find laptop under 70k and add to cart")
        self.assertEqual(plan_cart.target_action, "add_to_cart")

    # -------------------------------------------------------------
    # A6: Approve / Reject detection by strict regex fullmatch
    # -------------------------------------------------------------
    def test_a6_approval_prefix_does_not_hijack_search(self):
        """'Approved laptops under 50000' must be treated as a product search, NOT an approval."""
        plan = asi1_client._deterministic_extract("Approved laptops under 50000")
        self.assertEqual(plan.max_budget, 50000.0)

        # In process_user_text, this must invoke search and return product options, not an error about approval tokens
        import asyncio
        from unittest.mock import AsyncMock
        ctx = MagicMock()
        ctx.logger = MagicMock()

        reply = asyncio.run(process_user_text(ctx, "agent1_user", "Approved laptops under 50000"))
        # Must be comparison matrix, not approval error
        self.assertIn("Product Comparison & Decision Matrix", reply.text())
        self.assertNotIn("Please specify the approval token", reply.text())


    # -------------------------------------------------------------
    # A7: Seed validation in mailbox mode
    # -------------------------------------------------------------
    def test_a7_seed_validation_in_mailbox_mode(self):
        """validate_agent_config must return False when USE_AGENTVERSE=true and AGENT_SEED_PHRASE is unset."""
        from backend.uagent_app import validate_agent_config

        old_seed = os.environ.get("AGENT_SEED_PHRASE")
        old_mailbox = os.environ.get("USE_AGENTVERSE")
        try:
            os.environ["USE_AGENTVERSE"] = "true"
            os.environ["AGENT_SEED_PHRASE"] = ""
            self.assertFalse(validate_agent_config())

            os.environ["AGENT_SEED_PHRASE"] = "real seed phrase with twenty four words definitely present"
            self.assertTrue(validate_agent_config())

            os.environ["USE_AGENTVERSE"] = "false"
            os.environ["AGENT_SEED_PHRASE"] = ""
            self.assertTrue(validate_agent_config())
        finally:
            if old_seed is not None:
                os.environ["AGENT_SEED_PHRASE"] = old_seed
            else:
                os.environ.pop("AGENT_SEED_PHRASE", None)
            if old_mailbox is not None:
                os.environ["USE_AGENTVERSE"] = old_mailbox
            else:
                os.environ.pop("USE_AGENTVERSE", None)


if __name__ == "__main__":
    unittest.main()
