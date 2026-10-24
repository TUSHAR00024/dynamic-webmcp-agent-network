"""Tests for Unified Workflow Service, edge-case regressions, and security boundaries."""
import unittest
from unittest.mock import patch

from backend.bridge.bridge_security import BridgeSecurityManager
from backend.services.workflow_service import workflow_service
from backend.agents.policy_agent import policy_agent
from backend.models.product import ProductRecord, ProductSpecs
from backend.models.tool import ToolExecutionResult


class TestWorkflowAndRegressions(unittest.TestCase):

    def test_none_budget_handling(self):
        """Workflow should handle queries without explicit budgets smoothly without error."""
        result = workflow_service.run_search_and_compare(
            prompt="Recommend a top laptop for coding and software development",
            session_id="test_nobudget_session"
        )
        self.assertIn(result["status"], ["WAITING_FOR_APPROVAL", "COMPLETED"])
        self.assertTrue(len(result["candidates"]) > 0)
        self.assertIsNotNone(result["top_recommendation"])

    def test_no_products_found_graceful_handling(self):
        """Workflow should return a polite NO_RESULTS payload instead of raising an error when no items match."""
        result = workflow_service.run_search_and_compare(
            prompt="Find a laptop under ₹50 for programming",
            session_id="test_empty_session"
        )
        self.assertEqual(result["status"], "NO_RESULTS")
        self.assertEqual(result["candidates"], [])
        self.assertIsNone(result["approval_request"])
        self.assertIn("found under ₹50", result["message"])

    def test_exact_origin_allowlist_security(self):
        """Exact origin matching must reject adversarial prefixes/suffixes and only allow trusted origins."""
        # Malicious lookalikes
        self.assertFalse(BridgeSecurityManager.validate_origin("http://evil-localhost.com:8000"))
        self.assertFalse(BridgeSecurityManager.validate_origin("http://localhost.attacker.io:8000"))
        self.assertFalse(BridgeSecurityManager.validate_origin("https://techmart.example.com.phishing.org"))
        self.assertFalse(BridgeSecurityManager.validate_origin("http://127.0.0.1.badguy.com:5173"))
        self.assertFalse(BridgeSecurityManager.validate_origin("javascript:alert(1)"))

        # Valid allowed origins
        self.assertTrue(BridgeSecurityManager.validate_origin("http://localhost:8000"))
        self.assertTrue(BridgeSecurityManager.validate_origin("http://127.0.0.1:8000"))
        self.assertTrue(BridgeSecurityManager.validate_origin("https://techmart.example.com"))
        self.assertTrue(BridgeSecurityManager.validate_origin("https://asi1.ai"))
        self.assertTrue(BridgeSecurityManager.validate_origin("https://agentverse.ai"))

    def test_price_drift_rejection_on_approval(self):
        """If product price increases between approval issuance and execution, approval must be invalidated."""
        search_res = workflow_service.run_search_and_compare(
            prompt="Find a laptop under ₹70,000 for coding and add best to cart",
            session_id="drift_session",
            sender_address="agent1_legit_user"
        )
        approval_req = search_res.get("approval_request")
        self.assertIsNotNone(approval_req, "Approval request should have been generated for add_to_cart")

        approval_id = approval_req["approval_id"]
        bound_price = approval_req["bound_price"]

        # Mock tool_router.route_and_execute during verification to return an increased price
        drifted_price = bound_price + 3000.0  # ₹3,000 price surge

        mock_drifted_product_payload = {
            "product": {
                "id": approval_req["arguments"]["product_id"],
                "name": "Test Laptop",
                "price": drifted_price
            }
        }
        mock_tool_result = ToolExecutionResult(
            action_id="act_test_price",
            tool_id="tool_test",
            status="SUCCESS",
            tool_name="get_product_details",
            provider_id=approval_req["provider_id"],
            payload=mock_drifted_product_payload
        )

        with patch("backend.services.workflow_service.tool_router.route_and_execute", return_value=(mock_tool_result, {})):
            with self.assertRaises(ValueError) as ctx:
                workflow_service.execute_approved_action(approval_id, sender_address="agent1_legit_user")

            self.assertIn("Price changed", str(ctx.exception))
            token_record = policy_agent._tokens[approval_id]
            self.assertEqual(token_record["status"], "INVALIDATED")

    def test_approval_sender_binding_security(self):
        """Approval tokens cannot be hijacked by an attacker sending an execution request from another address."""
        search_res = workflow_service.run_search_and_compare(
            prompt="Find a laptop under ₹70,000 and add to cart",
            session_id="sender_binding_session",
            sender_address="agent1_legit_user"
        )
        approval_req = search_res["approval_request"]
        approval_id = approval_req["approval_id"]

        # Attacker tries to execute approval
        with self.assertRaises(PermissionError) as ctx:
            workflow_service.execute_approved_action(approval_id, sender_address="agent1_attacker_address")
        self.assertIn("different user session", str(ctx.exception))

    def test_approval_cancellation(self):
        """User can explicitly reject/cancel an approval token safely."""
        search_res = workflow_service.run_search_and_compare(
            prompt="Find a laptop under ₹70,000 and add to cart",
            session_id="cancel_session"
        )
        approval_id = search_res["approval_request"]["approval_id"]
        res = workflow_service.cancel_approval(approval_id)
        self.assertEqual(res["status"], "REJECTED")

        # Confirm token status in policy agent
        self.assertEqual(policy_agent._tokens[approval_id]["status"], "REJECTED")


if __name__ == "__main__":
    unittest.main()
