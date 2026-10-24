"""Dispatcher Master Agent: Connects ACP / ASI:One to the unified workflow pipeline."""
import logging
from typing import Any, Dict, Optional
from backend.protocols.acp_integration import ACPIntegrationService, ChatMessage
from backend.services.workflow_service import workflow_service

logger = logging.getLogger("Agents.Dispatcher")


class DispatcherAgent:
    def __init__(self):
        self.agent_name = "dispatcher_agent"

    def handle_user_prompt(
        self,
        prompt: str,
        session_id: str = "default_session",
        sender_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute search, multi-provider discovery, scoring, and approval preparation."""
        return workflow_service.run_search_and_compare(
            prompt=prompt,
            session_id=session_id,
            sender_address=sender_address
        )

    def execute_approved_action(
        self,
        approval_id: str,
        sender_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """Redeem approval token, execute verified cart mutation, and format ACP response."""
        result = workflow_service.execute_approved_action(
            approval_id=approval_id,
            sender_address=sender_address
        )

        summary_text = (
            f"Action verified and executed on {result['provider_id']}! "
            f"Added 1 unit to cart. {result['verification_details']} "
            f"Checkout boundary preserved: system stopped prior to order placement."
        )

        acp_msg = ACPIntegrationService.format_asi_response(
            task_summary=summary_text,
            details=result
        )

        return {
            "status": "SUCCESS",
            "verification_result": result,
            "acp_message": acp_msg.to_dict()
        }


dispatcher_agent = DispatcherAgent()
