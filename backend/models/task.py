"""Task, workflow state, and user constraints models."""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class WorkflowState(str, Enum):
    RECEIVED = "RECEIVED"
    PLANNING = "PLANNING"
    DISCOVERING = "DISCOVERING"
    ROUTING = "ROUTING"
    EXECUTING = "EXECUTING"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    CANCELLED = "CANCELLED"


@dataclass
class UserConstraints:
    category: str = "laptops"
    max_budget: Optional[float] = None
    min_budget: Optional[float] = None
    priorities: List[str] = field(default_factory=list)
    min_candidates: int = 3
    target_action: Optional[str] = None  # e.g. "add_to_cart"
    allow_checkout: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TaskStep:
    step_id: str
    task_id: str
    step_name: str
    assigned_agent: str
    status: str
    input_payload: Dict[str, Any] = field(default_factory=dict)
    output_payload: Dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0
    created_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Task:
    task_id: str
    session_id: str
    user_prompt: str
    constraints: UserConstraints
    state: WorkflowState = WorkflowState.RECEIVED
    planned_capabilities: List[str] = field(default_factory=list)
    selected_providers: List[str] = field(default_factory=list)
    current_step: str = "Initialized"
    steps: List[TaskStep] = field(default_factory=list)
    result_summary: Optional[str] = None
    error_message: Optional[str] = None
    created_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    updated_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["state"] = self.state.value if isinstance(self.state, WorkflowState) else self.state
        if isinstance(self.constraints, UserConstraints):
            d["constraints"] = self.constraints.to_dict()
        return d
