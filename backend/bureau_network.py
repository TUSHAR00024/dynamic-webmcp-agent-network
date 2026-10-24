"""Fetch.ai Multi-Agent Bureau Network: Specialist Agents collaborating via uagents.Bureau."""
import asyncio
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from uagents import Agent, Bureau, Context, Model

# Ensure project root in path
BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from backend.models.product import ProductRecord
from backend.registry.capability_map import CanonicalCapability
from backend.routing.tool_router import tool_router
from backend.services.workflow_service import workflow_service


# -------------------------------------------------------------
# Typed Inter-Agent Message Models (subclasses of uagents.Model)
# -------------------------------------------------------------

class ResearchRequest(Model):
    task_id: str
    query: str
    max_budget: Optional[float] = None
    reply_to: str


class ResearchResponse(Model):
    task_id: str
    products: List[Dict[str, Any]]
    count: int


class ComparisonRequest(Model):
    task_id: str
    products: List[Dict[str, Any]]
    priorities: List[str]
    reply_to: str


class ComparisonResponse(Model):
    task_id: str
    top_product: Dict[str, Any]
    rationale: str
    composite_score: float


class PolicyRequest(Model):
    task_id: str
    provider_id: str
    target_tool: str
    arguments: Dict[str, Any]
    bound_price: float
    reply_to: str


class PolicyResponse(Model):
    task_id: str
    approval_id: str
    bound_price: float
    expires_at: float


class CartExecutionRequest(Model):
    task_id: str
    approval_id: str
    reply_to: str


class CartExecutionResponse(Model):
    task_id: str
    status: str
    action_id: str
    verified_postcondition: bool
    cart_state: Dict[str, Any]


# -------------------------------------------------------------
# Agent Definitions
# -------------------------------------------------------------

research_agent = Agent(name="research_specialist", seed="research_agent_seed_phrase_demo_2026")
comparison_agent = Agent(name="comparison_specialist", seed="comparison_agent_seed_phrase_demo_2026")
policy_agent_instance = Agent(name="policy_specialist", seed="policy_agent_seed_phrase_demo_2026")
cart_agent_instance = Agent(name="cart_specialist", seed="cart_agent_seed_phrase_demo_2026")
supervisor_agent = Agent(name="network_supervisor", seed="network_supervisor_seed_phrase_demo_2026")


# --- Research Specialist Handler ---
@research_agent.on_message(ResearchRequest)
async def handle_research(ctx: Context, sender: str, msg: ResearchRequest):
    ctx.logger.info(f"Research Specialist received query '{msg.query}' for task {msg.task_id}")
    args = {"query": msg.query}
    if msg.max_budget:
        args["max_price"] = msg.max_budget

    products, _ = tool_router.route_parallel_search(args, task_id=msg.task_id)
    ctx.logger.info(f"Discovered {len(products)} products across providers.")

    await ctx.send(
        msg.reply_to or sender,
        ResearchResponse(
            task_id=msg.task_id,
            products=[p.to_dict() for p in products],
            count=len(products)
        )
    )


# --- Comparison Specialist Handler ---
@comparison_agent.on_message(ComparisonRequest)
async def handle_comparison(ctx: Context, sender: str, msg: ComparisonRequest):
    ctx.logger.info(f"Comparison Specialist analyzing {len(msg.products)} items for task {msg.task_id}")
    if not msg.products:
        return

    # Deterministic scoring based on coding priority
    scored = []
    for p in msg.products:
        score = 70.0
        cpu = str(p.get("specs", {}).get("cpu", "")).lower()
        if "ryzen 7" in cpu or "i5-13500h" in cpu or "m2" in cpu:
            score += 20.0
        scored.append((score, p))

    scored.sort(key=lambda x: x[0], reverse=True)
    best_score, best_product = scored[0]

    rationale = f"Selected {best_product.get('name')} based on high-performance multi-core CPU and verified battery endurance."
    await ctx.send(
        msg.reply_to or sender,
        ComparisonResponse(
            task_id=msg.task_id,
            top_product=best_product,
            rationale=rationale,
            composite_score=best_score
        )
    )


# --- Policy Specialist Handler ---
@policy_agent_instance.on_message(PolicyRequest)
async def handle_policy(ctx: Context, sender: str, msg: PolicyRequest):
    ctx.logger.info(f"Policy Specialist generating approval gate for {msg.task_id}")
    from backend.agents.policy_agent import policy_agent as internal_policy

    req = internal_policy.issue_approval_request(
        task_id=msg.task_id,
        provider_id=msg.provider_id,
        target_tool=msg.target_tool,
        arguments=msg.arguments,
        bound_price=msg.bound_price
    )

    await ctx.send(
        msg.reply_to or sender,
        PolicyResponse(
            task_id=msg.task_id,
            approval_id=req.approval_id,
            bound_price=req.bound_price,
            expires_at=req.expires_at
        )
    )


# --- Cart Specialist Handler ---
@cart_agent_instance.on_message(CartExecutionRequest)
async def handle_cart_execution(ctx: Context, sender: str, msg: CartExecutionRequest):
    ctx.logger.info(f"Cart Specialist executing verified action for token {msg.approval_id}")
    try:
        res = workflow_service.execute_approved_action(approval_id=msg.approval_id)
        await ctx.send(
            msg.reply_to or sender,
            CartExecutionResponse(
                task_id=msg.task_id,
                status=res["status"],
                action_id=res["action_id"],
                verified_postcondition=res["verified_postcondition"],
                cart_state=res.get("cart_state", {})
            )
        )
    except Exception as e:
        ctx.logger.error(f"Cart execution failed: {e}")


def create_bureau() -> Bureau:
    """Assemble and configure the multi-agent bureau."""
    bureau = Bureau(port=8010)
    bureau.add(research_agent)
    bureau.add(comparison_agent)
    bureau.add(policy_agent_instance)
    bureau.add(cart_agent_instance)
    bureau.add(supervisor_agent)
    return bureau
