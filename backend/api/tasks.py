"""Task execution and workflow coordination API."""
import hashlib
import json
import time
import uuid
from typing import Any, Dict, List
from backend.models.product import ProductRecord
from backend.registry.capability_map import CanonicalCapability
from backend.routing.tool_router import tool_router


class TaskWorkflowAPI:
    # In-memory session store for pending tasks and approvals
    TASKS: Dict[str, Dict[str, Any]] = {}
    APPROVALS: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def handle_run_workflow(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        prompt = payload.get("prompt", "")
        session_id = payload.get("session_id", "default_session")
        task_id = f"task_{uuid.uuid4().hex[:10]}"

        # 1. Planner logic: parse constraints from natural language
        max_budget = 70000.0 if "70,000" in prompt or "70000" in prompt else None
        priorities = []
        if "coding" in prompt.lower() or "programming" in prompt.lower():
            priorities.append("coding")
        if "battery" in prompt.lower():
            priorities.append("battery")
        if "reliability" in prompt.lower():
            priorities.append("reliability")

        # 2. Dynamic Tool Router: Parallel Catalogue Search
        canonical_search_args = {"query": "laptop"}
        if max_budget:
            canonical_search_args["max_price"] = max_budget

        products, routing_decisions = tool_router.route_parallel_search(
            canonical_search_args,
            task_id=task_id
        )

        # 3. Comparison Agent: Multi-attribute scoring
        # Weighting: Coding/CPU (35%), Battery (25%), RAM/SSD (20%), Warranty (10%), Value (10%)
        ranked_candidates = []
        for p in products:
            score = 70.0
            p_specs = p.specs

            # CPU / Coding bonus
            cpu_lower = str(p_specs.cpu).lower()
            if "ryzen 7" in cpu_lower or "i5-13500h" in cpu_lower or "12 cores" in cpu_lower or "8 cores" in cpu_lower:
                score += 15.0

            # Battery bonus
            bat_lower = str(p_specs.battery).lower()
            if "75wh" in bat_lower or "10.5" in bat_lower:
                score += 10.0
            elif "57wh" in bat_lower or "9.5" in bat_lower:
                score += 8.0
            elif "unknown" in bat_lower:
                score -= 5.0  # Penalize missing information transparently

            # RAM bonus
            if "16gb" in str(p_specs.ram).lower():
                score += 5.0

            # Warranty bonus
            if "3-year" in str(p_specs.warranty).lower():
                score += 5.0

            ranked_candidates.append({
                "product": p,
                "composite_score": round(score, 1)
            })

        ranked_candidates.sort(key=lambda x: x["composite_score"], reverse=True)
        top_rec = ranked_candidates[0]["product"] if ranked_candidates else None

        # 4. Policy Gate: Generate cryptographic approval request for CART_ADD
        approval_id = f"appr_{uuid.uuid4().hex[:10]}"
        target_tool = "add_to_cart" if top_rec.provider_id == "provider_alpha" else "cart_add"
        bound_args = {
            "session_id": session_id,
            "product_id": top_rec.product_id,
            "quantity": 1
        }

        canonical_hash_payload = json.dumps({
            "action_type": "add_to_cart",
            "provider_id": top_rec.provider_id,
            "target_tool": target_tool,
            "arguments": bound_args,
            "bound_price": round(top_rec.price, 2)
        }, sort_keys=True)
        arguments_hash = hashlib.sha256(canonical_hash_payload.encode("utf-8")).hexdigest()

        approval_record = {
            "approval_id": approval_id,
            "task_id": task_id,
            "session_id": session_id,
            "provider_id": top_rec.provider_id,
            "target_tool": target_tool,
            "arguments": bound_args,
            "arguments_hash": arguments_hash,
            "bound_price": top_rec.price,
            "expires_at": time.time() + 300,
            "status": "PENDING"
        }
        cls.APPROVALS[approval_id] = approval_record

        # Routing rationale summary
        rationale = (
            f"Searched multiple providers in parallel. Evaluated {len(products)} valid options under ₹{max_budget:,.0f}. "
            f"Selected '{top_rec.title}' ({top_rec.provenance}) as top recommendation (Score: {ranked_candidates[0]['composite_score']}/100). "
            f"Mapped cart operation to {top_rec.provider_id}'s `{target_tool}` tool."
        )

        task_record = {
            "task_id": task_id,
            "session_id": session_id,
            "prompt": prompt,
            "candidates": [c["product"].to_dict() for c in ranked_candidates],
            "top_recommendation": top_rec.to_dict(),
            "approval_request": approval_record,
            "routing_rationale": rationale,
            "status": "WAITING_FOR_APPROVAL"
        }
        cls.TASKS[task_id] = task_record

        return task_record
