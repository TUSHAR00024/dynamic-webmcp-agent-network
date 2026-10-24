"""Unified Workflow Service: Single source of truth for shopping execution and policy gates."""
import logging
import os
import time
import uuid
from typing import Any, Dict, List, Optional

from backend.agents.audit_agent import audit_agent
from backend.agents.cart_agent import cart_agent
from backend.agents.policy_agent import policy_agent
from backend.llm.asi1_client import asi1_client
from backend.models.product import ProductRecord
from backend.models.task import UserConstraints
from backend.protocols.acp_integration import ACPIntegrationService, ChatMessage
from backend.protocols.messages import (
    ActionExecutionMessage,
    ComparisonRequestMessage,
    ResearchQueryMessage
)
from backend.registry.capability_map import CanonicalCapability
from backend.routing.tool_router import tool_router
from backend.safety.idempotency import idempotency_guard

logger = logging.getLogger("Services.WorkflowService")


class WorkflowService:
    def __init__(self):
        # In-memory storage for active tasks
        self._tasks: Dict[str, Dict[str, Any]] = {}

    def run_search_and_compare(
        self,
        prompt: str,
        session_id: str = "default_session",
        sender_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute intent extraction, parallel multi-provider search, ranking & approval token generation."""
        task_id = f"task_{uuid.uuid4().hex[:10]}"
        sender = sender_address or "web_user"
        audit_agent.record_event(task_id, "TASK_INITIATED", "workflow_service", "RECEIVED", {"prompt": prompt, "sender": sender})

        # 1. Intent Extraction via ASI1 LLM (with deterministic fallback)
        plan = asi1_client.extract_intent_and_constraints(prompt)
        logger.info(f"[{task_id}] Extracted plan: query='{plan.query}', budget={plan.max_budget}, priorities={plan.priorities}")
        audit_agent.record_event(task_id, "PLAN_EXTRACTED", "asi1_client", "SUCCESS", plan.model_dump())

        # 2. Parallel Search across active providers via Dynamic Tool Router
        canonical_args: Dict[str, Any] = {"query": plan.query}
        if plan.max_budget is not None:
            canonical_args["max_price"] = plan.max_budget

        products, routing_decisions = tool_router.route_parallel_search(
            canonical_args,
            task_id=task_id
        )
        logger.info(f"[{task_id}] Router discovered {len(products)} products across providers.")
        audit_agent.record_event(task_id, "ROUTING_SEARCH", "tool_router", "SUCCESS", {"count": len(products)})

        # 3. Handle Empty Product Results gracefully (never raise)
        if not products:
            budget_str = f" under ₹{plan.max_budget:,.0f}" if plan.max_budget else ""
            msg = f"No {plan.category} found{budget_str}. Try increasing your budget limit or searching for a different model."
            return {
                "task_id": task_id,
                "session_id": session_id,
                "status": "NO_RESULTS",
                "message": msg,
                "candidates": [],
                "top_recommendation": None,
                "approval_request": None,
                "routing_rationale": msg
            }

        # 4. Multi-Attribute Candidate Scoring
        ranked_candidates = []
        for p in products:
            score = 65.0
            specs = p.specs

            # CPU / Coding priority
            cpu_lower = str(specs.cpu).lower()
            if any(k in cpu_lower for k in ["ryzen 7", "i5-13500h", "12 cores", "8 cores", "m2"]):
                score += 15.0
            elif "i5" in cpu_lower or "ryzen 5" in cpu_lower:
                score += 10.0

            # Battery priority
            bat_lower = str(specs.battery).lower()
            if "75wh" in bat_lower or "10.5" in bat_lower or "15 hours" in bat_lower:
                score += 10.0
            elif "57wh" in bat_lower or "9.5" in bat_lower or "65wh" in bat_lower:
                score += 8.0
            elif "unknown" in bat_lower:
                score -= 5.0  # Transparent penalty for uncertainty

            # RAM & Storage priority
            ram_lower = str(specs.ram).lower()
            if "16gb" in ram_lower or "unified" in ram_lower:
                score += 5.0

            # Warranty / Reliability priority
            if "3-year" in str(specs.warranty).lower():
                score += 5.0

            ranked_candidates.append({
                "product": p,
                "composite_score": round(score, 1)
            })

        ranked_candidates.sort(key=lambda x: x["composite_score"], reverse=True)
        top_rec = ranked_candidates[0]["product"]

        # 5. Generate Trade-off Explanation via ASI1 LLM
        rationale = asi1_client.generate_comparison_rationale(
            candidates=[r["product"].to_dict() for r in ranked_candidates],
            top_recommendation=top_rec.to_dict(),
            user_priorities=plan.priorities
        )

        # 6. Policy Approval Gate (if cart action requested)
        approval_msg = None
        if plan.target_action == "add_to_cart":
            target_tool = "add_to_cart" if top_rec.provider_id == "provider_alpha" else "cart_add"
            approval_msg = policy_agent.issue_approval_request(
                task_id=task_id,
                provider_id=top_rec.provider_id,
                target_tool=target_tool,
                arguments={
                    "session_id": session_id,
                    "product_id": top_rec.product_id,
                    "quantity": plan.quantity
                },
                bound_price=top_rec.price,
                session_id=session_id
            )
            # Bind the requesting sender address to the token
            record = policy_agent._tokens[approval_msg.approval_id]
            record["sender_address"] = sender

            audit_agent.record_event(
                task_id,
                "APPROVAL_ISSUED",
                "policy_agent",
                "PENDING",
                {"approval_id": approval_msg.approval_id, "bound_price": approval_msg.bound_price, "sender": sender}
            )

        task_data = {
            "task_id": task_id,
            "session_id": session_id,
            "sender_address": sender,
            "prompt": prompt,
            "plan": plan.model_dump(),
            "candidates": [r["product"].to_dict() for r in ranked_candidates],
            "top_recommendation": top_rec.to_dict(),
            "approval_request": approval_msg.to_dict() if approval_msg else None,
            "routing_rationale": rationale,
            "status": "WAITING_FOR_APPROVAL" if approval_msg else "COMPLETED"
        }
        self._tasks[task_id] = task_data
        return task_data

    def execute_approved_action(
        self,
        approval_id: str,
        sender_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """Validate token with price-drift & sender check, execute cart mutation, and verify state."""
        record = policy_agent._tokens.get(approval_id)
        if not record:
            raise ValueError(f"Approval token '{approval_id}' not found.")

        # 1. Sender Binding Check (prevent token hijacking)
        if sender_address and record.get("sender_address") and record["sender_address"] != "web_user":
            if record["sender_address"] != sender_address:
                raise PermissionError("Approval token belongs to a different user session.")

        # 2. Idempotency Check (prevent duplicate execution)
        existing = idempotency_guard.get_existing(approval_id)
        if existing:
            logger.info(f"Duplicate approval execution intercepted by idempotency guard for '{approval_id}'.")
            return existing

        # 3. Status and Expiry Check
        if record["status"] == "CONSUMED":
            raise ValueError(f"Approval token '{approval_id}' has already been consumed.")
        if record["status"] == "EXPIRED" or time.time() > record["expires_at"]:
            record["status"] = "EXPIRED"
            raise ValueError(f"Approval token '{approval_id}' has expired. Please ask me to search again.")
        if record["status"] != "PENDING":
            raise ValueError(f"Approval token '{approval_id}' is in status '{record['status']}'. Please ask me to search again.")

        # 4. Verify HMAC / Argument Hash integrity
        import hmac
        expected_hash = policy_agent.compute_hmac(
            task_id=record["task_id"],
            provider_id=record["provider_id"],
            target_tool=record["target_tool"],
            arguments=record["arguments"],
            bound_price=record["bound_price"]
        )
        if not hmac.compare_digest(record.get("arguments_hash", ""), expected_hash):
            record["status"] = "TAMPERED"
            raise ValueError(f"Approval token '{approval_id}' signature verification failed: arguments or price were modified.")

        # 5. Live Authoritative Price Re-Check (fail closed)
        pid = record["arguments"].get("product_id")
        provider_id = record["provider_id"]
        task_id = record["task_id"]

        detail_res, _ = tool_router.route_and_execute(
            canonical_capability=CanonicalCapability.PRODUCT_DETAILS,
            canonical_args={"product_id": pid},
            preferred_provider_id=provider_id,
            task_id=task_id
        )

        if detail_res.status != "SUCCESS":
            # Fail closed: live price cannot be retrieved
            raise ValueError(
                f"PRICE_UNVERIFIABLE: Authoritative live product details could not be retrieved from provider '{provider_id}' "
                f"(status: {detail_res.status}). Action aborted; token remains PENDING for retry."
            )

        raw_p = detail_res.payload.get("product") or detail_res.payload.get("item") or {}
        if "price" not in raw_p and "cost" not in raw_p:
            # Fail closed: missing price field
            raise ValueError(
                f"PRICE_UNVERIFIABLE: Live product details from provider '{provider_id}' missing price information. "
                "Action aborted; token remains PENDING for retry."
            )

        try:
            live_price = float(raw_p.get("price") if "price" in raw_p else raw_p["cost"])
        except (ValueError, TypeError):
            raise ValueError(
                f"PRICE_UNVERIFIABLE: Invalid price format returned by provider '{provider_id}'. "
                "Action aborted; token remains PENDING for retry."
            )

        # Wire in PRICE_DRIFT_TOLERANCE_PERCENT (default 0.0%)
        tolerance_pct = float(os.getenv("PRICE_DRIFT_TOLERANCE_PERCENT", "0.0"))
        max_allowed_delta = (record["bound_price"] * (tolerance_pct / 100.0)) + 0.01

        if abs(live_price - record["bound_price"]) > max_allowed_delta:
            record["status"] = "INVALIDATED"
            audit_agent.record_event(task_id, "PRICE_DRIFT_INVALIDATED", "policy_agent", "INVALIDATED", {
                "bound_price": record["bound_price"],
                "live_price": live_price,
                "tolerance_pct": tolerance_pct
            })
            raise ValueError(
                f"Price changed from ₹{record['bound_price']:,.2f} to ₹{live_price:,.2f}. "
                "Previous approval is invalidated. A new approval is required."
            )

        # 5. Execute Action on Target Provider
        exec_msg = ActionExecutionMessage(
            task_id=task_id,
            approval_id=approval_id,
            provider_id=provider_id,
            target_tool=record["target_tool"],
            arguments=record["arguments"]
        )

        try:
            ver_res = cart_agent.execute_and_verify_cart_action(exec_msg)
        except Exception as e:
            attempts = record.get("attempts", 0) + 1
            record["attempts"] = attempts
            if attempts >= 2:
                record["status"] = "FAILED"
            else:
                record["status"] = "PENDING"  # Safe retry permitted
            audit_agent.record_event(task_id, "ACTION_FAILED", "cart_agent", "FAILED", {"error": str(e), "attempts": attempts})
            raise RuntimeError(f"Cart action execution failed on provider (attempt {attempts}/2): {str(e)}")

        # 6. Verify Postcondition (fail closed if item is not verified)
        if not ver_res.verified_postcondition:
            record["status"] = "FAILED_VERIFICATION"
            audit_agent.record_event(task_id, "ACTION_VERIFICATION_FAILED", "cart_agent", "FAILED_VERIFICATION", {
                "approval_id": approval_id,
                "verification_details": ver_res.verification_details
            })
            raise RuntimeError(
                f"Cart addition could not be verified: {ver_res.verification_details} "
                "Cart state is unknown. No checkout occurred."
            )

        # 7. Consume Token ONLY after verified success
        record["status"] = "CONSUMED"
        audit_agent.record_event(task_id, "APPROVAL_CONSUMED", "policy_agent", "CONSUMED", {"approval_id": approval_id})
        audit_agent.record_event(task_id, "ACTION_VERIFIED", "cart_agent", ver_res.status, {"verified_postcondition": True})

        cart_state = ver_res.cart_state
        result = {
            "status": "SUCCESS",
            "action_id": ver_res.action_id,
            "provider_id": provider_id,
            "tool_name": record["target_tool"],
            "verified_postcondition": True,
            "verification_details": ver_res.verification_details,
            "cart_state": cart_state,
            "checkout_boundary_preserved": True
        }

        # Cache in idempotency guard
        idempotency_guard.record_execution(approval_id, result)
        return result

    def cancel_approval(self, approval_id: str, sender_address: Optional[str] = None) -> Dict[str, Any]:
        """Cancel or reject a pending approval."""
        record = policy_agent._tokens.get(approval_id)
        if not record:
            raise ValueError(f"Approval token '{approval_id}' not found.")

        # Sender binding check
        if sender_address and record.get("sender_address") and record["sender_address"] != "web_user":
            if record["sender_address"] != sender_address:
                raise PermissionError("Approval token belongs to a different user session.")

        # Only PENDING tokens can be cancelled
        if record["status"] != "PENDING":
            raise ValueError(f"Cannot cancel approval token '{approval_id}': token is already in status '{record['status']}'.")

        record["status"] = "REJECTED"
        audit_agent.record_event(record["task_id"], "APPROVAL_REJECTED", "policy_agent", "REJECTED", {"approval_id": approval_id})
        return {"status": "REJECTED", "approval_id": approval_id, "message": "Action rejected. Cart remains untouched."}


workflow_service = WorkflowService()
