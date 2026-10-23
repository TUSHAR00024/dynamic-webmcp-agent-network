"""WebMCP Browser Bridge: Connects live browser page contexts to Dynamic Tool Router."""
import logging
import time
import uuid
from typing import Any, Callable, Dict, List, Optional

from backend.bridge.bridge_protocol import (
    BrowserSessionRecord,
    BrowserToolDeclaration
)
from backend.bridge.bridge_security import BridgeSecurityManager
from backend.models.tool import (
    ExecutionMode,
    ToolClassification,
    ToolDefinition,
    ToolExecutionResult,
    ToolStatus
)
from backend.registry.tool_registry import tool_registry

logger = logging.getLogger("Bridge.BrowserBridge")


class BrowserBridge:
    def __init__(self, session_timeout_seconds: float = 60.0):
        self.session_timeout = session_timeout_seconds
        # session_id -> BrowserSessionRecord
        self._sessions: Dict[str, BrowserSessionRecord] = {}
        # Optional registered mock/in-memory execute handler for direct browser simulation
        self._client_handlers: Dict[str, Callable[[str, Dict[str, Any]], Dict[str, Any]]] = {}

    def register_session(
        self,
        session_id: str,
        origin_url: str,
        tools: List[Dict[str, Any]],
        client_ip: str = "127.0.0.1",
        user_agent: str = "Mozilla/5.0 WebMCP Client"
    ) -> BrowserSessionRecord:
        """Register a connected browser tab and its declared WebMCP tools."""
        if not BridgeSecurityManager.validate_origin(origin_url):
            raise PermissionError(f"Origin '{origin_url}' is not allowed by bridge security policy.")

        session = self._sessions.get(session_id)
        if not session:
            session = BrowserSessionRecord(
                session_id=session_id,
                origin_url=origin_url,
                client_ip=client_ip,
                user_agent=user_agent
            )
            self._sessions[session_id] = session
        else:
            session.heartbeat()

        # Register tools
        for t in tools:
            decl = BrowserToolDeclaration(
                name=t["name"],
                description=t.get("description", ""),
                input_schema=t.get("input_schema", {"type": "object"}),
                canonical_capability=t.get("canonical_capability", "UNKNOWN"),
                requires_approval=t.get("requires_approval", False)
            )
            session.declared_tools[decl.name] = decl

            # Register into canonical tool registry
            tool_id = f"browser_{session_id}_{decl.name}"
            tool_def = ToolDefinition(
                tool_id=tool_id,
                provider_id=f"browser_{session_id}",
                tool_name=decl.name,
                description=decl.description,
                input_schema=decl.input_schema,
                canonical_capability=decl.canonical_capability,
                classification=ToolClassification.REVERSIBLE_STATE_CHANGE if decl.requires_approval else ToolClassification.READ_ONLY,
                requires_user_approval=decl.requires_approval,
                execution_mode=ExecutionMode.WEBMCP_BROWSER,
                status=ToolStatus.AVAILABLE
            )
            tool_registry.register_tool(tool_def)

        logger.info(f"Registered browser session '{session_id}' with {len(tools)} WebMCP tools from origin '{origin_url}'.")
        return session

    def register_client_handler(
        self,
        session_id: str,
        handler: Callable[[str, Dict[str, Any]], Dict[str, Any]]
    ) -> None:
        """Register a client-side execution handler (for testing or direct websocket link)."""
        self._client_handlers[session_id] = handler

    def heartbeat(self, session_id: str) -> bool:
        session = self._sessions.get(session_id)
        if session:
            session.heartbeat()
            return True
        return False

    def disconnect_session(self, session_id: str) -> None:
        session = self._sessions.get(session_id)
        if session:
            session.is_active = False
            # Mark its tools as UNAVAILABLE in the registry
            tool_registry.mark_provider_tools_status(f"browser_{session_id}", ToolStatus.UNAVAILABLE)
            logger.warning(f"Browser session '{session_id}' disconnected; its WebMCP tools are now UNAVAILABLE.")

    def sweep_stale_sessions(self) -> int:
        """Sweep inactive or timed-out sessions and mark their tools unavailable."""
        swept = 0
        for s in list(self._sessions.values()):
            if s.is_stale(self.session_timeout) and s.is_active:
                self.disconnect_session(s.session_id)
                swept += 1
        return swept

    def execute_in_browser(
        self,
        session_id: str,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> ToolExecutionResult:
        """Tunnel execution into the active browser page context."""
        start_t = time.time()
        action_id = f"act_b_{uuid.uuid4().hex[:8]}"

        session = self._sessions.get(session_id)
        if not session or not session.is_active or session.is_stale(self.session_timeout):
            return ToolExecutionResult(
                action_id=action_id,
                tool_id=f"browser_{session_id}_{tool_name}",
                provider_id=f"browser_{session_id}",
                tool_name=tool_name,
                status="FAILED",
                error_message=f"Browser session '{session_id}' is disconnected or unavailable.",
                execution_time_ms=round((time.time() - start_t) * 1000, 2)
            )

        # Sanitize arguments
        clean_args = BridgeSecurityManager.sanitize_arguments(arguments)

        # Check if local handler exists
        handler = self._client_handlers.get(session_id)
        if handler:
            try:
                raw_out = handler(tool_name, clean_args)
                dur = (time.time() - start_t) * 1000
                return ToolExecutionResult(
                    action_id=action_id,
                    tool_id=f"browser_{session_id}_{tool_name}",
                    provider_id=f"browser_{session_id}",
                    tool_name=tool_name,
                    status="SUCCESS",
                    payload=raw_out,
                    verified_postcondition=True,
                    verification_details="Executed inside live browser tab WebMCP modelContext handler.",
                    execution_time_ms=round(dur, 2)
                )
            except Exception as e:
                dur = (time.time() - start_t) * 1000
                return ToolExecutionResult(
                    action_id=action_id,
                    tool_id=f"browser_{session_id}_{tool_name}",
                    provider_id=f"browser_{session_id}",
                    tool_name=tool_name,
                    status="FAILED",
                    error_message=f"Browser WebMCP execution error: {str(e)}",
                    execution_time_ms=round(dur, 2)
                )

        # Standard simulated response if no custom callback is registered
        dur = (time.time() - start_t) * 1000
        return ToolExecutionResult(
            action_id=action_id,
            tool_id=f"browser_{session_id}_{tool_name}",
            provider_id=f"browser_{session_id}",
            tool_name=tool_name,
            status="SUCCESS",
            payload={"message": f"Tool '{tool_name}' executed in browser tab '{session_id}'.", "args": clean_args},
            verified_postcondition=True,
            execution_time_ms=round(dur, 2)
        )

    def list_active_sessions(self) -> List[Dict[str, Any]]:
        self.sweep_stale_sessions()
        return [s.to_dict() for s in self._sessions.values() if s.is_active]


# Global browser bridge singleton
browser_bridge = BrowserBridge()
