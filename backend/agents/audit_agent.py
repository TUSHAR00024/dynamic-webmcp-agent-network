"""Audit Specialist Agent: Verifiable audit trails and privacy redaction."""
import time
from typing import Any, Dict, List
from backend.models.audit_event import AuditEvent


class AuditAgent:
    def __init__(self):
        self.agent_name = "audit_agent"
        self._events: List[AuditEvent] = []

    def record_event(
        self,
        task_id: str,
        event_type: str,
        action_or_tool: str,
        status: str,
        details: Dict[str, Any]
    ) -> AuditEvent:
        # Sanitize sensitive keys (passwords, tokens, seed phrases)
        clean_details = {}
        for k, v in details.items():
            if any(s in k.lower() for s in ["token", "seed", "secret", "password", "key"]):
                clean_details[k] = "[REDACTED]"
            else:
                clean_details[k] = v

        event = AuditEvent(
            event_id=f"evt_{len(self._events) + 1}",
            task_id=task_id,
            agent_name=self.agent_name,
            event_type=event_type,
            action_or_tool=action_or_tool,
            status=status,
            details=clean_details
        )
        self._events.append(event)
        return event

    def get_task_trace(self, task_id: str) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self._events if e.task_id == task_id]


audit_agent = AuditAgent()
