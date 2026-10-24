"""Approvals API: Exposes verified execution to HTTP endpoints."""
from typing import Any, Dict
from backend.services.workflow_service import workflow_service


class ApprovalsAPI:
    @classmethod
    def handle_execute_approval(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        approval_id = payload.get("approval_id")
        sender = payload.get("sender_address", "web_user")
        if not approval_id:
            raise ValueError("Missing 'approval_id' in request.")
        return workflow_service.execute_approved_action(approval_id, sender_address=sender)

    @classmethod
    def handle_reject_approval(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        approval_id = payload.get("approval_id")
        sender = payload.get("sender_address", "web_user")
        if not approval_id:
            raise ValueError("Missing 'approval_id' in request.")
        return workflow_service.cancel_approval(approval_id, sender_address=sender)
