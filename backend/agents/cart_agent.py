"""Cart Action Specialist Agent: Executes approved mutations with postcondition verification."""
import uuid
from typing import Any, Dict
from backend.protocols.messages import (
    ActionExecutionMessage,
    ActionVerificationResultMessage
)
from backend.registry.capability_map import CanonicalCapability
from backend.registry.schema_normalizer import SchemaNormalizer
from backend.routing.tool_router import tool_router


class CartActionAgent:
    def __init__(self):
        self.agent_name = "cart_agent"

    def execute_and_verify_cart_action(self, msg: ActionExecutionMessage) -> ActionVerificationResultMessage:
        # 1. Execute state-changing cart tool via router
        res, decision = tool_router.route_and_execute(
            canonical_capability=CanonicalCapability.CART_ADD,
            canonical_args=msg.arguments,
            preferred_provider_id=msg.provider_id,
            task_id=msg.task_id
        )

        if res.status != "VERIFIED" and res.status != "SUCCESS":
            raise RuntimeError(f"Cart tool execution failed on provider '{msg.provider_id}': {res.error_message}")

        # 2. Independent postcondition verification: Read back cart from provider
        cart_res, _ = tool_router.route_and_execute(
            canonical_capability=CanonicalCapability.CART_READ,
            canonical_args={"session_id": msg.arguments.get("session_id", "default_session")},
            preferred_provider_id=msg.provider_id,
            task_id=msg.task_id
        )

        cart_payload = cart_res.payload if cart_res.status == "SUCCESS" else {}
        canonical_cart = SchemaNormalizer.normalize_cart_state(msg.provider_id, cart_payload)
        items = canonical_cart.items

        # Confirm target item is present in read-back state
        target_pid = msg.arguments.get("product_id") or msg.arguments.get("item_sku") or msg.arguments.get("sku")
        verified_item = any(i.product_id == target_pid or i.sku == target_pid for i in items)

        if verified_item:
            details = (
                f"Successfully added {msg.arguments.get('quantity', 1)} unit(s) of '{target_pid}' to {msg.provider_id}'s cart. "
                f"Independent CART_READ query confirmed state reflects {len(items)} line item(s)."
            )
        else:
            details = (
                f"Postcondition verification failed: '{target_pid}' was not found in provider {msg.provider_id}'s cart after CART_ADD. "
                f"Cart state reflects {len(items)} line item(s)."
            )

        return ActionVerificationResultMessage(
            action_id=res.action_id,
            task_id=msg.task_id,
            sender_agent=self.agent_name,
            target_agent="audit_agent",
            status="VERIFIED" if verified_item else "UNVERIFIED",
            verified_postcondition=verified_item,
            verification_details=details,
            cart_state=canonical_cart.to_dict()
        )


cart_agent = CartActionAgent()
