"""Tool models and classification for Dynamic WebMCP Agent Network."""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ToolClassification(str, Enum):
    READ_ONLY = "read_only"
    REVERSIBLE_STATE_CHANGE = "reversible_state_change"
    CONSEQUENTIAL_ACTION = "consequential_action"
    FINANCIAL = "financial"


class ExecutionMode(str, Enum):
    WEBMCP_BROWSER = "webmcp_browser"
    REMOTE_MCP = "remote_mcp"
    DEMO_ADAPTER = "demo_adapter"


class ToolStatus(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    DEPRECATED = "deprecated"
    ERROR = "error"


@dataclass
class ToolDefinition:
    tool_id: str
    provider_id: str
    tool_name: str
    description: str
    input_schema: Dict[str, Any]
    canonical_capability: str
    classification: ToolClassification = ToolClassification.READ_ONLY
    requires_user_approval: bool = False
    execution_mode: ExecutionMode = ExecutionMode.DEMO_ADAPTER
    status: ToolStatus = ToolStatus.AVAILABLE
    discovered_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    latency_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["classification"] = self.classification.value if isinstance(self.classification, ToolClassification) else self.classification
        d["execution_mode"] = self.execution_mode.value if isinstance(self.execution_mode, ExecutionMode) else self.execution_mode
        d["status"] = self.status.value if isinstance(self.status, ToolStatus) else self.status
        return d


@dataclass
class ToolExecutionResult:
    action_id: str
    tool_id: str
    provider_id: str
    tool_name: str
    status: str  # "SUCCESS", "FAILED", "VERIFIED"
    payload: Dict[str, Any] = field(default_factory=dict)
    verified_postcondition: bool = False
    verification_details: Optional[str] = None
    error_message: Optional[str] = None
    execution_time_ms: float = 0.0
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
