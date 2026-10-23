"""Research Specialist Agent: Queries products across discovered providers."""
from typing import Any, Dict, List
from backend.models.product import ProductRecord
from backend.protocols.messages import ResearchQueryMessage, ResearchResultMessage
from backend.routing.tool_router import tool_router


class ResearchAgent:
    def __init__(self):
        self.agent_name = "research_agent"

    def execute_research(self, msg: ResearchQueryMessage) -> ResearchResultMessage:
        args = {"query": msg.query or "laptop"}
        if msg.max_budget:
            args["max_price"] = msg.max_budget

        products, _ = tool_router.route_parallel_search(args, task_id=msg.task_id)

        return ResearchResultMessage(
            correlation_id=msg.correlation_id,
            sender_agent=self.agent_name,
            target_agent="comparison_agent",
            task_id=msg.task_id,
            products=[p.to_dict() for p in products]
        )


research_agent = ResearchAgent()
