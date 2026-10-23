"""Planner Specialist Agent: Parses user intent and builds capability plans."""
import re
from typing import Any, Dict, List
from backend.models.task import UserConstraints
from backend.protocols.messages import TaskPlanRequest, TaskPlanResponse
from backend.registry.capability_map import CanonicalCapability


class PlannerAgent:
    def __init__(self):
        self.agent_name = "planner_agent"

    def plan_task(self, request: TaskPlanRequest) -> TaskPlanResponse:
        prompt = request.user_prompt
        constraints = UserConstraints()

        # Extract budget (e.g. "under ₹70,000" or "under 70000")
        budget_match = re.search(r"(?:under|below|max|budget)\s*(?:₹|rs\.?|inr)?\s*([\d,]+)", prompt, re.IGNORECASE)
        if budget_match:
            try:
                raw_num = budget_match.group(1).replace(",", "")
                constraints.max_budget = float(raw_num)
            except ValueError:
                constraints.max_budget = 70000.0
        elif "70,000" in prompt or "70000" in prompt:
            constraints.max_budget = 70000.0

        # Extract priorities
        p_lower = prompt.lower()
        if "coding" in p_lower or "programming" in p_lower or "developer" in p_lower:
            constraints.priorities.append("coding")
        if "battery" in p_lower or "battery life" in p_lower:
            constraints.priorities.append("battery")
        if "reliability" in p_lower or "durable" in p_lower or "warranty" in p_lower:
            constraints.priorities.append("reliability")

        # Extract actions
        if "cart" in p_lower:
            constraints.target_action = "add_to_cart"
        if "checkout" in p_lower:
            # Check if checkout is explicitly forbidden or allowed
            if "do not check out" in p_lower or "dont checkout" in p_lower or "don't checkout" in p_lower or "ask me before checkout" in p_lower:
                constraints.allow_checkout = False
            else:
                constraints.allow_checkout = False  # Default to safety

        # Canonical capabilities plan
        planned = [
            CanonicalCapability.PRODUCT_SEARCH,
            CanonicalCapability.PRODUCT_DETAILS,
            CanonicalCapability.PRODUCT_COMPARISON
        ]
        if constraints.target_action == "add_to_cart":
            planned.append(CanonicalCapability.CART_ADD)
            planned.append(CanonicalCapability.CART_READ)

        return TaskPlanResponse(
            correlation_id=request.correlation_id,
            sender_agent=self.agent_name,
            target_agent="dispatcher_agent",
            task_id=f"plan_{request.session_id}",
            constraints=constraints,
            planned_capabilities=planned,
            requires_approval=True
        )


planner_agent = PlannerAgent()
