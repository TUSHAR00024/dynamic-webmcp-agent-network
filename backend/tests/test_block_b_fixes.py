"""Regression tests for BLOCK B fixes: Security and correctness of approval workflow."""
import time
import unittest
from unittest.mock import patch, MagicMock

from backend.services.workflow_service import workflow_service
from backend.agents.policy_agent import policy_agent
from backend.safety.idempotency import idempotency_guard
from backend.protocols.messages import ActionVerificationResultMessage


class TestBlockBFixes(unittest.TestCase):

    # -------------------------------------------------------------
    # B1: Ownership check and state corruption prevention in cancel
    # -------------------------------------------------------------
    def test_b1_cancel_approval_sender_ownership_check(self):
        """Foreign sender cannot cancel another user's approval token."""
        search_res = workflow_service.run_search_and_compare(
            prompt="Find a laptop under 70000 and add to cart",
            session_id="b1_sess_1",
            sender_address="agent1_legit_owner"
        )
        approval_id = search_res["approval_request"]["approval_id"]

        # Attacker tries to cancel
        with self.assertRaises(PermissionError) as ctx:
            workflow_service.cancel_approval(approval_id, sender_address="agent1_attacker_address")
        self.assertIn("different user session", str(ctx.exception))
        # Status must remain PENDING
        self.assertEqual(policy_agent._tokens[approval_id]["status"], "PENDING")

    def test_b1_cannot_cancel_consumed_token(self):
        """Cancelling an already CONSUMED token must raise an error and leave status unchanged."""
        search_res = workflow_service.run_search_and_compare(
            prompt="Find a laptop under 70000 and add to cart",
            session_id="b1_sess_2",
            sender_address="agent1_user"
        )
        approval_id = search_res["approval_request"]["approval_id"]

        # Legitimate execution
        res = workflow_service.execute_approved_action(approval_id, sender_address="agent1_user")
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(policy_agent._tokens[approval_id]["status"], "CONSUMED")

        # Now attempt to cancel
        with self.assertRaises(ValueError) as ctx:
            workflow_service.cancel_approval(approval_id, sender_address="agent1_user")
        self.assertIn("already in status 'CONSUMED'", str(ctx.exception))
        self.assertEqual(policy_agent._tokens[approval_id]["status"], "CONSUMED")

    # -------------------------------------------------------------
    # B2: Failed execution can be safely retried once
    # -------------------------------------------------------------
    def test_b2_failed_execution_safe_retry(self):
        """First provider tool call fails -> token remains PENDING (attempt 1); second call succeeds."""
        search_res = workflow_service.run_search_and_compare(
            prompt="Find a laptop under 70000 and add to cart",
            session_id="b2_retry_sess",
            sender_address="agent1_user"
        )
        approval_id = search_res["approval_request"]["approval_id"]

        # 1. First execution fails with transient network error
        with patch("backend.services.workflow_service.cart_agent.execute_and_verify_cart_action", side_effect=RuntimeError("Transient 504 Timeout")):
            with self.assertRaises(RuntimeError) as ctx:
                workflow_service.execute_approved_action(approval_id, sender_address="agent1_user")
            self.assertIn("Transient 504 Timeout", str(ctx.exception))

        # Token must still be PENDING with attempt count 1
        record = policy_agent._tokens[approval_id]
        self.assertEqual(record["status"], "PENDING")
        self.assertEqual(record["attempts"], 1)

        # 2. Second execution retry succeeds
        retry_res = workflow_service.execute_approved_action(approval_id, sender_address="agent1_user")
        self.assertEqual(retry_res["status"], "SUCCESS")
        self.assertEqual(record["status"], "CONSUMED")

    # -------------------------------------------------------------
    # B3: Expiry and HMAC argument tamper detection
    # -------------------------------------------------------------
    def test_b3_expired_token_returns_search_again(self):
        """Expired approval tokens must reject execution with a friendly search-again message."""
        search_res = workflow_service.run_search_and_compare(
            prompt="Find a laptop under 70000 and add to cart",
            session_id="b3_expire_sess",
            sender_address="agent1_user"
        )
        approval_id = search_res["approval_request"]["approval_id"]
        # Manually expire token
        policy_agent._tokens[approval_id]["expires_at"] = time.time() - 10.0

        with self.assertRaises(ValueError) as ctx:
            workflow_service.execute_approved_action(approval_id, sender_address="agent1_user")

        self.assertIn("has expired", str(ctx.exception))
        self.assertIn("ask me to search again", str(ctx.exception))

    def test_b3_hmac_tamper_detection(self):
        """Tampering with token arguments or price must invalidate HMAC signature and abort."""
        search_res = workflow_service.run_search_and_compare(
            prompt="Find a laptop under 70000 and add to cart",
            session_id="b3_tamper_sess",
            sender_address="agent1_user"
        )
        approval_id = search_res["approval_request"]["approval_id"]

        # Attacker tampers with the arguments dict in the token record
        policy_agent._tokens[approval_id]["arguments"]["quantity"] = 99  # Tampered quantity

        with self.assertRaises(ValueError) as ctx:
            workflow_service.execute_approved_action(approval_id, sender_address="agent1_user")

        self.assertIn("signature verification failed", str(ctx.exception))
        self.assertEqual(policy_agent._tokens[approval_id]["status"], "TAMPERED")


if __name__ == "__main__":
    unittest.main()
