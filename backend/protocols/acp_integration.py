"""Agent Chat Protocol (ACP) integration for ASI:One and Agentverse."""
from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Attempt official uagents_core ACP imports if installed in environment
try:
    from uagents_core.contrib.protocols.chat import (
        ChatMessage as OfficialChatMessage,
        ChatAcknowledgement as OfficialChatAck,
        TextContent as OfficialTextContent,
        chat_protocol_spec as official_spec
    )
    HAS_OFFICIAL_ACP = True
except ImportError:
    HAS_OFFICIAL_ACP = False
    official_spec = {
        "name": "AgentChatProtocol",
        "version": "0.3.0",
        "description": "Standard Chat Protocol for autonomous agents on Agentverse and ASI:One."
    }


@dataclass
class TextContent:
    text: str
    type: str = "text"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ResourceContent:
    uri: str
    mime_type: str = "application/json"
    metadata: Dict[str, Any] = field(default_factory=dict)
    type: str = "resource"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ChatMessage:
    msg_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    content: List[Dict[str, Any]] = field(default_factory=list)

    @classmethod
    def create_text(cls, text: str) -> ChatMessage:
        return cls(content=[TextContent(text=text).to_dict()])

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ChatAcknowledgement:
    acknowledged_msg_id: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ACPIntegrationService:
    @staticmethod
    def format_asi_response(task_summary: str, details: Optional[Dict[str, Any]] = None) -> ChatMessage:
        """Format a rich conversational response adhering to ACP specifications."""
        content = [TextContent(text=task_summary).to_dict()]
        if details:
            content.append(ResourceContent(
                uri="urn:webpilot:task:details",
                mime_type="application/json",
                metadata=details
            ).to_dict())

        return ChatMessage(content=content)

    @staticmethod
    def get_protocol_metadata() -> Dict[str, Any]:
        return {
            "name": "AgentChatProtocol",
            "version": "0.3.0",
            "has_official_sdk": HAS_OFFICIAL_ACP,
            "capabilities": [
                "natural_language_intake",
                "structured_cards",
                "human_in_the_loop_approval",
                "postcondition_verification"
            ]
        }
