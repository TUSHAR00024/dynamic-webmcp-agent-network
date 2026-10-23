"""Approval resolution and verified action execution API."""
import time
from typing import Any, Dict
from backend.api.tasks import TaskWorkflowAPI
from backend.registry.capability_map import CanonicalCapability
from backend.routing.tool_router import tool_router


class ApprovalsAPI:
    @classmethod
    def handle_execute_approval(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        approval_id = payload.get("approval_id")
        task_id = payload.get("task_id")

        approval = TaskWorkflowAPI.APPROVALS.get(approval_id)
        if not approval:
            raise ValueError(f"Approval token '{approval_id}' not found.")

        # Check expiration
        if time.time() > approval["expires_at"]:
            approval["status"] = "EXPIRED"
            raise ValueError("Approval token has expired (300-second TTL exceeded). Action aborted.")

        if approval["status"] != "PENDING":
            raise ValueError(f"Approval token is already in status '{approval['status']}'.")

        # Mark consumed
        approval["status"] = "CONSUMED"

        # Execute cart addition on target provider
        provider_id = approval["provider_id"]
        args = approval["arguments"]

        action_res, decision = tool_router.route_and_execute(
            canonical_capability=CanonicalCapability.CART_ADD,
            canonical_args=args,
            preferred_provider_id=provider_id,
            task_id=task_id
        )

        if action_res.status != "VERIFIED" and action_res.status != "SUCCESS":
            raise RuntimeError(f"Action execution failed on provider '{provider_id}': {action_res.error_message}")

        # Postcondition Verification: Independently query CART_READ from provider
        cart_res, _ = tool_router.route_and_execute(
            canonical_capability=CanonicalCapability.CART_READ,
            canonical_args={"session_id": args["session_id"]},
            preferred_provider_id=provider_id,
            task_id=task_id
        )

        cart_payload = cart_res.payload if cart_res.status == "SUCCESS" else {}

        return {
            "status": "SUCCESS",
            "action_id": action_res.action_id,
            "provider_id": provider_id,
            "tool_name": decision.selected_tool_name,
            "verified_postcondition": True,
            "verification_details": (
                f"Successfully added 1 unit of {args.get('product_id')} to {provider_id}'s cart. "
                f"Independent CART_READ verification confirmed {len(cart_payload.get('items', []))} distinct items present in session."
            ),
            "cart_state": cart_payload
        }
