"""Policy Specialist Agent: Enforces human-in-the-loop approval and token binding."""
import hashlib
import json
import time
import uuid
from typing import Any, Dict
from backend.protocols.messages import (
    PolicyApprovalRequestMessage,
    PolicyApprovalResponseMessage
)


class PolicyAgent:
    def __init__(self):
        self.agent_name = "policy_agent"
        # approval_id -> record
        self._tokens: Dict[str, Dict[str, Any]] = {}

    def issue_approval_request(
        self,
        task_id: str,
        provider_id: str,
        target_tool: str,
        arguments: Dict[str, Any],
        bound_price: float,
        session_id: str = "default_session"
    ) -> PolicyApprovalRequestMessage:
        """Issue cryptographically bound approval token for state-changing action."""
        appr_id = f"appr_{uuid.uuid4().hex[:10]}"
        expires_at = time.time() + 300.0  # 5 minutes TTL

        # Compute canonical hash
        canonical = json.dumps({
            "task_id": task_id,
            "provider_id": provider_id,
            "target_tool": target_tool,
            "arguments": arguments,
            "bound_price": round(bound_price, 2)
        }, sort_keys=True)
        token_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

        record = {
            "approval_id": appr_id,
            "task_id": task_id,
            "session_id": session_id,
            "provider_id": provider_id,
            "target_tool": target_tool,
            "arguments": arguments,
            "arguments_hash": token_hash,
            "bound_price": bound_price,
            "expires_at": expires_at,
            "status": "PENDING"
        }
        self._tokens[appr_id] = record

        return PolicyApprovalRequestMessage(
            sender_agent=self.agent_name,
            target_agent="dispatcher_agent",
            task_id=task_id,
            approval_id=appr_id,
            action_type="CART_ADD",
            provider_id=provider_id,
            target_tool=target_tool,
            arguments=arguments,
            arguments_hash=token_hash,
            bound_price=bound_price,
            expires_at=expires_at
        )

    def validate_and_consume(
        self,
        approval_id: str,
        current_product_price: float
    ) -> Dict[str, Any]:
        """Validate token integrity, expiration, and price binding before consuming."""
        record = self._tokens.get(approval_id)
        if not record:
            raise ValueError(f"Approval token '{approval_id}' not found.")

        if time.time() > record["expires_at"]:
            record["status"] = "EXPIRED"
            raise ValueError(f"Approval token '{approval_id}' has expired. Action aborted.")

        if record["status"] != "PENDING":
            raise ValueError(f"Approval token '{approval_id}' is already in status '{record['status']}'.")

        # Zero tolerance price check
        if abs(current_product_price - record["bound_price"]) > 0.01:
            record["status"] = "INVALIDATED"
            raise ValueError(f"Price changed from ₹{record['bound_price']} to ₹{current_product_price}. Approval invalidated.")

        record["status"] = "CONSUMED"
        return record


policy_agent = PolicyAgent()
