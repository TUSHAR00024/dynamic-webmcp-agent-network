"""Typed message envelopes for multi-agent inter-process communication."""
from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional
from backend.models.product import ProductRecord
from backend.models.task import UserConstraints


@dataclass
class AgentMessageBase:
    message_id: str = field(default_factory=lambda: f"msg_{uuid.uuid4().hex[:10]}")
    correlation_id: str = field(default_factory=lambda: f"corr_{uuid.uuid4().hex[:10]}")
    sender_agent: str = ""
    target_agent: str = ""
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TaskPlanRequest(AgentMessageBase):
    user_prompt: str = ""
    session_id: str = ""


@dataclass
class TaskPlanResponse(AgentMessageBase):
    task_id: str = ""
    constraints: UserConstraints = field(default_factory=UserConstraints)
    planned_capabilities: List[str] = field(default_factory=list)
    requires_approval: bool = True


@dataclass
class DiscoveryQueryMessage(AgentMessageBase):
    target_origins: List[str] = field(default_factory=list)


@dataclass
class DiscoveryResultMessage(AgentMessageBase):
    discovered_tools_count: int = 0
    active_providers: List[str] = field(default_factory=list)


@dataclass
class ResearchQueryMessage(AgentMessageBase):
    task_id: str = ""
    category: str = "laptops"
    max_budget: Optional[float] = None
    query: str = ""


@dataclass
class ResearchResultMessage(AgentMessageBase):
    task_id: str = ""
    products: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ComparisonRequestMessage(AgentMessageBase):
    task_id: str = ""
    candidates: List[Dict[str, Any]] = field(default_factory=list)
    constraints: UserConstraints = field(default_factory=UserConstraints)


@dataclass
class ComparisonResultMessage(AgentMessageBase):
    task_id: str = ""
    ranked_candidates: List[Dict[str, Any]] = field(default_factory=list)
    top_recommendation: Optional[Dict[str, Any]] = None
    rationale: str = ""


@dataclass
class PolicyApprovalRequestMessage(AgentMessageBase):
    task_id: str = ""
    approval_id: str = ""
    action_type: str = "CART_ADD"
    provider_id: str = ""
    target_tool: str = ""
    arguments: Dict[str, Any] = field(default_factory=dict)
    arguments_hash: str = ""
    bound_price: float = 0.0
    expires_at: float = 0.0


@dataclass
class PolicyApprovalResponseMessage(AgentMessageBase):
    approval_id: str = ""
    approved: bool = False
    rejection_reason: Optional[str] = None


@dataclass
class ActionExecutionMessage(AgentMessageBase):
    task_id: str = ""
    approval_id: str = ""
    provider_id: str = ""
    target_tool: str = ""
    arguments: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ActionVerificationResultMessage(AgentMessageBase):
    action_id: str = ""
    task_id: str = ""
    status: str = "VERIFIED"
    verified_postcondition: bool = True
    verification_details: str = ""
    cart_state: Dict[str, Any] = field(default_factory=dict)
