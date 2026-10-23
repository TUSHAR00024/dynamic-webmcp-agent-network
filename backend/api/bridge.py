"""WebMCP Bridge API endpoints."""
import json
from typing import Any, Dict
from backend.adapters.webmcp_adapter import WebMCPBrowserAdapter
from backend.bridge.browser_bridge import browser_bridge
from backend.routing.tool_router import tool_router


class BridgeAPI:
    @staticmethod
    def handle_register(payload: Dict[str, Any]) -> Dict[str, Any]:
        session_id = payload.get("session_id", "default_browser_session")
        origin_url = payload.get("origin_url", "http://localhost:8000")
        tools = payload.get("tools", [])

        session = browser_bridge.register_session(
            session_id=session_id,
            origin_url=origin_url,
            tools=tools
        )

        # Register a WebMCP adapter on the router if not already registered
        adapter_id = f"browser_{session_id}"
        if adapter_id not in tool_router._adapters:
            adapter = WebMCPBrowserAdapter(session_id=session_id, origin_url=origin_url)
            tool_router.register_adapter(adapter)

        return {
            "status": "SUCCESS",
            "session_id": session.session_id,
            "registered_tools_count": len(session.declared_tools),
            "origin_url": session.origin_url
        }

    @staticmethod
    def handle_heartbeat(payload: Dict[str, Any]) -> Dict[str, Any]:
        session_id = payload.get("session_id")
        if not session_id:
            return {"status": "ERROR", "message": "Missing session_id"}
        ok = browser_bridge.heartbeat(session_id)
        return {"status": "SUCCESS" if ok else "NOT_FOUND"}

    @staticmethod
    def handle_list_sessions() -> Dict[str, Any]:
        sessions = browser_bridge.list_active_sessions()
        return {"sessions": sessions, "count": len(sessions)}
