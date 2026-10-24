"""Task API: Exposes workflow service to HTTP endpoints."""
from typing import Any, Dict
from backend.services.workflow_service import workflow_service


class TaskWorkflowAPI:
    @classmethod
    def handle_run_workflow(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        prompt = payload.get("prompt", "")
        session_id = payload.get("session_id", "default_session")
        sender = payload.get("sender_address", "web_user")
        return workflow_service.run_search_and_compare(
            prompt=prompt,
            session_id=session_id,
            sender_address=sender
        )
