"""Agentverse registration and manifest publishing configuration."""
import os
from typing import Any, Dict


class AgentverseConfig:
    AGENTVERSE_MAILBOX_URL = os.getenv("AGENTVERSE_MAILBOX_URL", "https://agentverse.ai/v1/mailbox")
    AGENTVERSE_API_KEY = os.getenv("AGENTVERSE_API_KEY", "")
    DISPATCHER_SEED = os.getenv("DISPATCHER_SEED", "dynamic-webmcp-dispatcher-seed-2026")
    AGENT_NAME = "dynamic_webmcp_operator"

    @classmethod
    def generate_agent_manifest(cls) -> Dict[str, Any]:
        """Generate manifest for Agentverse Explorer publication and ASI:One discoverability."""
        return {
            "name": cls.AGENT_NAME,
            "display_name": "Dynamic WebMCP Agent Operator",
            "version": "1.0.0",
            "description": "Autonomous multi-agent web operator with dynamic runtime WebMCP & Remote MCP tool discovery, cross-provider routing, and human-in-the-loop approval.",
            "protocol": "AgentChatProtocol v0.3.0",
            "tags": ["web-operator", "webmcp", "mcp", "shopping", "dynamic-routing", "asi-one"],
            "endpoints": [
                {
                    "type": "chat",
                    "url": "http://127.0.0.1:8000/api/tasks/run_workflow"
                }
            ],
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
