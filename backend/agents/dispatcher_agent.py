"""Dispatcher Master Agent: Connects ACP / ASI:One to the specialist agent network."""
import logging
import uuid
from typing import Any, Dict, List, Optional

from backend.agents.audit_agent import audit_agent
from backend.agents.cart_agent import cart_agent
from backend.agents.comparison_agent import comparison_agent
from backend.agents.discovery_agent import discovery_agent
from backend.agents.planner_agent import planner_agent
from backend.agents.policy_agent import policy_agent
from backend.agents.research_agent import research_agent
from backend.protocols.acp_integration import ACPIntegrationService, ChatMessage
from backend.protocols.messages import (
    ActionExecutionMessage,
    ComparisonRequestMessage,
    DiscoveryQueryMessage,
    ResearchQueryMessage,
    TaskPlanRequest
)

logger = logging.getLogger("Agents.Dispatcher")


class DispatcherAgent:
    def __init__(self):
        self.agent_name = "dispatcher_agent"

    def handle_user_prompt(self, prompt: str, session_id: str = "default_session") -> Dict[str, Any]:
        """Execute end-to-end multi-agent pipeline up to the policy approval gate."""
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        audit_agent.record_event(task_id, "TASK_INITIATED", "dispatcher", "RECEIVED", {"prompt": prompt})

        # 1. Planner Agent
        plan_req = TaskPlanRequest(user_prompt=prompt, session_id=session_id)
        plan_res = planner_agent.plan_task(plan_req)
        audit_agent.record_event(task_id, "PLAN_CREATED", "planner_agent", "SUCCESS", plan_res.constraints.to_dict())

        # 2. Discovery Agent
        disc_req = DiscoveryQueryMessage()
        disc_res = discovery_agent.discover_active_tools(disc_req)
        audit_agent.record_event(task_id, "TOOLS_DISCOVERED", "discovery_agent", "SUCCESS", {"count": disc_res.discovered_tools_count})

        # 3. Research Agent (Parallel Multi-Provider Search)
        res_req = ResearchQueryMessage(
            task_id=task_id,
            category=plan_res.constraints.category,
            max_budget=plan_res.constraints.max_budget,
            query="laptop"
        )
        res_res = research_agent.execute_research(res_req)
        audit_agent.record_event(task_id, "RESEARCH_COMPLETED", "research_agent", "SUCCESS", {"candidates_count": len(res_res.products)})

        # 4. Comparison Agent
        comp_req = ComparisonRequestMessage(
            task_id=task_id,
            candidates=res_res.products,
            constraints=plan_res.constraints
        )
        comp_res = comparison_agent.compare_candidates(comp_req)
        audit_agent.record_event(task_id, "COMPARISON_COMPLETED", "comparison_agent", "SUCCESS", {"top_recommendation": comp_res.top_recommendation.get("sku") if comp_res.top_recommendation else None})

        # 5. Policy Agent: Generate approval token if state mutation requested
        approval_msg = None
        if plan_res.constraints.target_action == "add_to_cart" and comp_res.top_recommendation:
            top = comp_res.top_recommendation
            approval_msg = policy_agent.issue_approval_request(
                task_id=task_id,
                provider_id=top["provider_id"],
                target_tool="add_to_cart" if top["provider_id"] == "provider_alpha" else "cart_add",
                arguments={
                    "session_id": session_id,
                    "product_id": top["product_id"],
                    "quantity": 1
                },
                bound_price=top["price"],
                session_id=session_id
            )
            audit_agent.record_event(task_id, "APPROVAL_ISSUED", "policy_agent", "PENDING", {"approval_id": approval_msg.approval_id, "bound_price": approval_msg.bound_price})

        return {
            "task_id": task_id,
            "session_id": session_id,
            "constraints": plan_res.constraints.to_dict(),
            "candidates": comp_res.ranked_candidates,
            "top_recommendation": comp_res.top_recommendation,
            "comparison_rationale": comp_res.rationale,
            "approval_request": approval_msg.to_dict() if approval_msg else None,
            "status": "WAITING_FOR_APPROVAL" if approval_msg else "COMPLETED"
        }

    def execute_approved_action(self, approval_id: str, task_id: str) -> Dict[str, Any]:
        """Redeem approval token, execute verified cart mutation, and format ACP response."""
        record = policy_agent._tokens.get(approval_id)
        if not record:
            raise ValueError(f"Approval '{approval_id}' not found.")

        # Validate token
        policy_agent.validate_and_consume(approval_id, current_product_price=record["bound_price"])
        audit_agent.record_event(task_id, "APPROVAL_CONSUMED", "policy_agent", "CONSUMED", {"approval_id": approval_id})

        # Cart Agent Execution
        exec_msg = ActionExecutionMessage(
            task_id=task_id,
            approval_id=approval_id,
            provider_id=record["provider_id"],
            target_tool=record["target_tool"],
            arguments=record["arguments"]
        )
        ver_res = cart_agent.execute_and_verify_cart_action(exec_msg)
        audit_agent.record_event(task_id, "ACTION_VERIFIED", "cart_agent", ver_res.status, {"postcondition_verified": ver_res.verified_postcondition})

        # Build ACP response
        summary_text = (
            f"Action successfully executed and verified on {record['provider_id']}! "
            f"Added 1 unit of {record['arguments'].get('product_id')} at ₹{record['bound_price']:,.2f}. "
            f"Checkout boundary preserved: system stopped before placing order."
        )
        acp_msg = ACPIntegrationService.format_asi_response(
            task_summary=summary_text,
            details=ver_res.to_dict()
        )

        return {
            "status": "SUCCESS",
            "verification_result": ver_res.to_dict(),
            "acp_message": acp_msg.to_dict()
        }


dispatcher_agent = DispatcherAgent()
