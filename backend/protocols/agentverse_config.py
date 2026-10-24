"""Agentverse registration and manifest publishing configuration."""
import os
from typing import Any, Dict


class AgentverseConfig:
    AGENTVERSE_MAILBOX_URL = os.getenv("AGENTVERSE_MAILBOX_URL", "https://agentverse.ai/v1/mailbox")
    AGENTVERSE_API_KEY = os.getenv("AGENTVERSE_API_KEY", "")
    AGENT_SEED_PHRASE = os.getenv("AGENT_SEED_PHRASE", "")
    AGENT_NAME = os.getenv("AGENT_NAME", "dynamic_webmcp_operator")

    @classmethod
    def generate_agent_manifest(cls, agent_address: str = "") -> Dict[str, Any]:
        """Generate manifest for Agentverse Explorer publication and ASI:One discoverability."""
        return {
            "name": cls.AGENT_NAME,
            "display_name": "Dynamic WebMCP Agent Operator",
            "version": "1.0.0",
            "address": agent_address or "agent1q...",
            "description": "Autonomous multi-agent web operator with dynamic runtime WebMCP & Remote MCP tool discovery, cross-provider routing, and human-in-the-loop approval.",
            "protocol": "AgentChatProtocol v0.3.0",
            "tags": ["web-operator", "webmcp", "mcp", "shopping", "dynamic-routing", "asi-one", "innovationlab", "hackathon"],
            "capabilities": [
                "PRODUCT_SEARCH",
                "PRODUCT_DETAILS",
                "PRODUCT_COMPARISON",
                "CART_ADD",
                "CART_READ",
                "HUMAN_APPROVAL_GATE"
            ],
            "is_public": True
        }
