"""Cryptographic Approval Token Generation, HMAC-SHA256 Verification, and Lifecycle Management."""
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
import uuid
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger("Safety.Approvals")

# Server-side secret for HMAC-SHA256 signing
_DEFAULT_SECRET = secrets.token_bytes(32)


def get_hmac_secret() -> bytes:
    """Retrieve HMAC secret from environment or process fallback."""
    env_secret = os.getenv("APPROVAL_HMAC_SECRET", "").encode("utf-8")
    return env_secret if env_secret else _DEFAULT_SECRET


def compute_hmac_signature(
    task_id: str,
    provider_id: str,
    target_tool: str,
    arguments: Dict[str, Any],
    bound_price: float,
    secret: Optional[bytes] = None
) -> str:
    """Compute cryptographically secure HMAC-SHA256 signature for action payload."""
    sec = secret or get_hmac_secret()
    canonical_payload = json.dumps({
        "task_id": str(task_id),
        "provider_id": str(provider_id),
        "target_tool": str(target_tool),
        "arguments": arguments,
        "bound_price": round(float(bound_price), 2)
    }, sort_keys=True)
    return hmac.new(sec, canonical_payload.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_hmac_signature(
    expected_signature: str,
    task_id: str,
    provider_id: str,
    target_tool: str,
    arguments: Dict[str, Any],
    bound_price: float,
    secret: Optional[bytes] = None
) -> bool:
    """Verify HMAC signature using timing-attack resistant comparison."""
    calculated = compute_hmac_signature(
        task_id=task_id,
        provider_id=provider_id,
        target_tool=target_tool,
        arguments=arguments,
        bound_price=bound_price,
        secret=secret
    )
    return hmac.compare_digest(expected_signature, calculated)


class ApprovalTokenStore:
    """In-memory cryptographic approval token store with TTL enforcement."""

    def __init__(self):
        self._tokens: Dict[str, Dict[str, Any]] = {}

    def issue_token(
        self,
        task_id: str,
        provider_id: str,
        target_tool: str,
        arguments: Dict[str, Any],
        bound_price: float,
        session_id: str = "default_session",
        sender_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """Issue an HMAC-bound approval token with TTL and sender binding."""
        approval_id = f"appr_{uuid.uuid4().hex[:10]}"
        ttl_seconds = float(os.getenv("APPROVAL_TTL_SECONDS", "300.0"))
        expires_at = time.time() + ttl_seconds

        signature = compute_hmac_signature(
            task_id=task_id,
            provider_id=provider_id,
            target_tool=target_tool,
            arguments=arguments,
            bound_price=bound_price
        )

        record = {
            "approval_id": approval_id,
            "task_id": task_id,
            "session_id": session_id,
            "provider_id": provider_id,
            "target_tool": target_tool,
            "arguments": dict(arguments),
            "arguments_hash": signature,
            "bound_price": bound_price,
            "expires_at": expires_at,
            "status": "PENDING",
            "attempts": 0,
            "sender_address": sender_address or "web_user"
        }
        self._tokens[approval_id] = record
        return record

    def get_token(self, approval_id: str) -> Optional[Dict[str, Any]]:
        return self._tokens.get(approval_id)

    def validate_and_consume(
        self,
        approval_id: str,
        current_price: float,
        sender_address: Optional[str] = None
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """Validate token state, sender binding, expiration, HMAC signature, and price drift."""
        record = self._tokens.get(approval_id)
        if not record:
            return False, f"Approval token '{approval_id}' not found.", None

        if record["status"] != "PENDING":
            return False, f"Token '{approval_id}' is already {record['status']}.", record

        if time.time() > record["expires_at"]:
            record["status"] = "EXPIRED"
            return False, f"Approval token '{approval_id}' has expired.", record

        if sender_address and record.get("sender_address"):
            if sender_address != record["sender_address"]:
                return False, f"Sender '{sender_address}' does not match bound requester.", record

        # Verify HMAC signature integrity
        valid_hmac = verify_hmac_signature(
            expected_signature=record["arguments_hash"],
            task_id=record["task_id"],
            provider_id=record["provider_id"],
            target_tool=record["target_tool"],
            arguments=record["arguments"],
            bound_price=record["bound_price"]
        )
        if not valid_hmac:
            record["status"] = "TAMPERED"
            return False, f"HMAC signature verification failed for token '{approval_id}'.", record

        # Zero-tolerance price drift check
        tolerance = float(os.getenv("PRICE_DRIFT_TOLERANCE_PERCENT", "0.0"))
        max_allowed = record["bound_price"] * (1.0 + tolerance)
        if current_price > max_allowed:
            record["status"] = "INVALIDATED"
            return False, f"Price increased from ₹{record['bound_price']} to ₹{current_price}.", record

        record["status"] = "CONSUMED"
        return True, "Valid", record


# Global singleton store
approval_store = ApprovalTokenStore()


class ApprovalsAPI:
    """API bridge for executing or rejecting approvals."""

    @classmethod
    def handle_execute_approval(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        from backend.services.workflow_service import workflow_service
        approval_id = payload.get("approval_id")
        sender = payload.get("sender_address", "web_user")
        if not approval_id:
            raise ValueError("Missing 'approval_id' in request.")
        return workflow_service.execute_approved_action(approval_id, sender_address=sender)

    @classmethod
    def handle_reject_approval(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        from backend.services.workflow_service import workflow_service
        approval_id = payload.get("approval_id")
        sender = payload.get("sender_address", "web_user")
        if not approval_id:
            raise ValueError("Missing 'approval_id' in request.")
        return workflow_service.cancel_approval(approval_id, sender_address=sender)
