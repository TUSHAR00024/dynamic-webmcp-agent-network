"""Policy Specialist Agent: Enforces human-in-the-loop approval and token binding."""
import hashlib
import hmac
import json
import os
import secrets
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
        secret_env = os.getenv("APPROVAL_HMAC_SECRET", "").encode("utf-8")
        self._server_secret = secret_env if secret_env else secrets.token_bytes(32)
        # approval_id -> record
        self._tokens: Dict[str, Dict[str, Any]] = {}

    def compute_hmac(
        self,
        task_id: str,
        provider_id: str,
        target_tool: str,
        arguments: Dict[str, Any],
        bound_price: float
    ) -> str:
        """Compute cryptographically secure HMAC-SHA256 signature for action payload."""
        canonical = json.dumps({
            "task_id": task_id,
            "provider_id": provider_id,
            "target_tool": target_tool,
            "arguments": arguments,
            "bound_price": round(bound_price, 2)
        }, sort_keys=True)
        return hmac.new(self._server_secret, canonical.encode("utf-8"), hashlib.sha256).hexdigest()

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
        ttl_seconds = float(os.getenv("APPROVAL_TTL_SECONDS", "300.0"))
        expires_at = time.time() + ttl_seconds

        token_hash = self.compute_hmac(
            task_id=task_id,
            provider_id=provider_id,
            target_tool=target_tool,
            arguments=arguments,
            bound_price=bound_price
        )

        record = {
            "approval_id": appr_id,
            "task_id": task_id,
            "session_id": session_id,
            "provider_id": provider_id,
            "target_tool": target_tool,
            "arguments": dict(arguments),
            "arguments_hash": token_hash,
            "bound_price": bound_price,
            "expires_at": expires_at,
            "status": "PENDING",
            "attempts": 0
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
            raise ValueError(f"Approval token '{approval_id}' has expired. Please ask me to search again.")

        if record["status"] != "PENDING":
            raise ValueError(f"Approval token '{approval_id}' is already in status '{record['status']}'.")

        # Verify HMAC integrity
        expected_hash = self.compute_hmac(
            task_id=record["task_id"],
            provider_id=record["provider_id"],
            target_tool=record["target_tool"],
            arguments=record["arguments"],
            bound_price=record["bound_price"]
        )
        if not hmac.compare_digest(record.get("arguments_hash", ""), expected_hash):
            record["status"] = "TAMPERED"
            raise ValueError(f"Approval token '{approval_id}' signature invalid: arguments or parameters tampered.")

        # Zero tolerance price check
        if abs(current_product_price - record["bound_price"]) > 0.01:
            record["status"] = "INVALIDATED"
            raise ValueError(f"Price changed from ₹{record['bound_price']} to ₹{current_product_price}. Approval invalidated.")

        record["status"] = "CONSUMED"
        return record


policy_agent = PolicyAgent()
