"""Bridge Protocol specifications for Browser WebMCP communication."""
from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class BridgeMessageType(str, Enum):
    REGISTER_SESSION = "register_session"
    HEARTBEAT = "heartbeat"
    TOOL_REGISTRATION = "tool_registration"
    TOOL_INVOCATION = "tool_invocation"
    TOOL_RESULT = "tool_result"
    DISCONNECT = "disconnect"


@dataclass
class BrowserToolDeclaration:
    name: str
    description: str
    input_schema: Dict[str, Any]
    canonical_capability: str
    requires_approval: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BrowserSessionRecord:
    session_id: str
    origin_url: str
    client_ip: str
    user_agent: str
    declared_tools: Dict[str, BrowserToolDeclaration] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    last_heartbeat: float = field(default_factory=time.time)
    is_active: bool = True

    def heartbeat(self) -> None:
        self.last_heartbeat = time.time()
        self.is_active = True

    def is_stale(self, timeout_seconds: float = 60.0) -> bool:
        return (time.time() - self.last_heartbeat) > timeout_seconds

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "origin_url": self.origin_url,
            "client_ip": self.client_ip,
            "user_agent": self.user_agent,
            "declared_tools": {k: v.to_dict() for k, v in self.declared_tools.items()},
            "is_active": not self.is_stale(),
            "tools_count": len(self.declared_tools),
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.created_at)),
            "last_heartbeat": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.last_heartbeat))
        }


@dataclass
class BridgeInvocationEnvelope:
    call_id: str
    session_id: str
    tool_name: str
    arguments: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
