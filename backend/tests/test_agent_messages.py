"""Unit tests for Multi-Agent Orchestration and ACP Response Flow."""
import unittest
from backend.agents.dispatcher_agent import dispatcher_agent
from backend.agents.planner_agent import planner_agent
from backend.protocols.acp_integration import ACPIntegrationService, ChatMessage
from backend.protocols.messages import TaskPlanRequest


class TestAgentOrchestration(unittest.TestCase):
    def test_planner_extracts_constraints(self):
        prompt = (
            "Find the best laptop under ₹70,000 for programming and college. "
            "Prioritize coding performance, battery life, and reliability. "
            "Compare at least three options, explain trade-offs, and add the best option to my cart. Do not check out."
        )
        plan_req = TaskPlanRequest(user_prompt=prompt, session_id="test_sess_1")
        plan_res = planner_agent.plan_task(plan_req)

        self.assertEqual(plan_res.constraints.max_budget, 70000.0)
        self.assertIn("coding", plan_res.constraints.priorities)
        self.assertIn("battery", plan_res.constraints.priorities)
        self.assertEqual(plan_res.constraints.target_action, "add_to_cart")
        self.assertFalse(plan_res.constraints.allow_checkout)

    def test_dispatcher_end_to_end_pipeline_and_approval_gate(self):
        prompt = "Find a laptop under ₹70,000 for coding and add to cart."
        workflow = dispatcher_agent.handle_user_prompt(prompt, session_id="test_sess_2")

        self.assertEqual(workflow["status"], "WAITING_FOR_APPROVAL")
        self.assertIsNotNone(workflow["top_recommendation"])
        self.assertGreaterEqual(len(workflow["candidates"]), 3)
        self.assertIsNotNone(workflow["approval_request"])

        # Execute approved action
        appr_id = workflow["approval_request"]["approval_id"]
        task_id = workflow["task_id"]

        result = dispatcher_agent.execute_approved_action(appr_id, task_id)
        self.assertEqual(result["status"], "SUCCESS")
        self.assertTrue(result["verification_result"]["verified_postcondition"])

        # Check ACP Message formatting
        acp_msg = result["acp_message"]
        self.assertIn("content", acp_msg)
        self.assertGreaterEqual(len(acp_msg["content"]), 1)
        self.assertEqual(acp_msg["content"][0]["type"], "text")
        self.assertIn("Checkout boundary preserved", acp_msg["content"][0]["text"])

    def test_acp_integration_metadata(self):
        meta = ACPIntegrationService.get_protocol_metadata()
        self.assertEqual(meta["name"], "AgentChatProtocol")
        self.assertEqual(meta["version"], "0.3.0")
        self.assertIn("human_in_the_loop_approval", meta["capabilities"])

    def test_chat_acknowledgement_resilience_to_legacy_payloads(self):
        """Verify that ChatAcknowledgement deserializes both legacy {'acknowledged': true} and modern payloads."""
        import json
        from uuid import uuid4
        from uagents_core.contrib.protocols.chat import ChatAcknowledgement

        # 1. Payload with 'acknowledged': True and timestamp
        legacy_payload = json.dumps({"timestamp": "2026-10-24T15:13:14Z", "acknowledged": True})
        ack1 = ChatAcknowledgement.parse_raw(legacy_payload)
        self.assertIsNotNone(ack1.acknowledged_msg_id)

        # 2. Payload with only 'acknowledged': True
        bare_payload = json.dumps({"acknowledged": True})
        ack2 = ChatAcknowledgement.parse_raw(bare_payload)
        self.assertIsNotNone(ack2.acknowledged_msg_id)

        # 3. Modern payload with acknowledged_msg_id
        test_uuid = str(uuid4())
        modern_payload = json.dumps({"timestamp": "2026-10-24T15:13:14Z", "acknowledged_msg_id": test_uuid})
        ack3 = ChatAcknowledgement.parse_raw(modern_payload)
        self.assertEqual(str(ack3.acknowledged_msg_id), test_uuid)


if __name__ == "__main__":
    unittest.main()
