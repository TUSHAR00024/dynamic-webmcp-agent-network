"""Audit event and routing decision records."""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class RoutingDecisionRecord:
    decision_id: str
    task_id: str
    required_capability: str
    considered_providers: List[str]
    excluded_providers: Dict[str, str]  # provider_id -> reason
    scores: Dict[str, float]  # provider_id -> score
    selected_provider_id: str
    selected_tool_name: str
    rationale: str
    execution_mode: str
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AuditEvent:
    event_id: str
    task_id: str
    agent_name: str
    event_type: str
    action_or_tool: str
    status: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
