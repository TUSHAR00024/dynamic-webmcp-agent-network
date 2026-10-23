# Agentverse & ASI:One Integration Setup Guide

## 1. Overview
The **Dynamic WebMCP Agent Network** exposes an ACP (Agent Chat Protocol) compliant endpoint that interfaces with **ASI:One** and can be registered on **Agentverse**.

---

## 2. Agent Chat Protocol (ACP) Specifications
The agent implements ACP v0.3.0 as defined by `uagents_core.contrib.protocols.chat`:
- **Protocol Name**: `AgentChatProtocol`
- **Protocol Version**: `0.3.0`
- **Digest**: `proto:agent_chat_protocol_v0_3_0_webpilot`
- **Primary Message Models**:
  - `ChatMessage`: Wraps user prompt or agent reply blocks with unique `msg_id` and UTC `timestamp`.
  - `TextContent`: Standard conversational text payload (`type: "text"`, `text: str`).
  - `ResourceContent`: Structured metadata payload (`type: "resource"`, `uri: str`, `metadata: dict`).
  - `ChatAcknowledgement`: Delivery confirmation returned for incoming messages.

---

## 3. Registering the Agent on Agentverse

Follow these steps to register the agent on the Fetch.ai Agentverse platform:

1. **Log in to Agentverse**:
   - Navigate to [https://agentverse.ai](https://agentverse.ai) and sign in.
2. **Create a Managed Agent or Mailbox**:
   - For locally hosted agents: Select **Local Agents** -> **Set up Mailbox**.
   - Copy your `AGENTVERSE_API_KEY` and mailbox URL.
3. **Configure Environment Variables**:
   In your `.env` file:
   ```bash
   USE_AGENTVERSE=true
   AGENTVERSE_API_KEY=your_agentverse_key_here
   AGENTVERSE_MAILBOX_URL=https://agentverse.ai/v1/mailbox
   DISPATCHER_SEED=your-secret-unique-seed-phrase
   ```
4. **Publish Manifest to Agentverse Explorer**:
   The manifest generated in `backend/protocols/agentverse_config.py` can be submitted to make the agent discoverable on ASI:One:
   ```json
   {
     "name": "dynamic_webmcp_operator",
     "display_name": "Dynamic WebMCP Agent Operator",
     "version": "1.0.0",
     "description": "Autonomous multi-agent web operator with dynamic runtime WebMCP & Remote MCP tool discovery, cross-provider routing, and human-in-the-loop approval.",
     "protocol": "AgentChatProtocol v0.3.0",
     "tags": ["web-operator", "webmcp", "mcp", "shopping", "dynamic-routing", "asi-one"]
   }
   ```
5. **Verify Discovery on ASI:One**:
   - Open ASI:One (`https://asi1.ai`).
   - Query `@dynamic_webmcp_operator Find the best laptop under ₹70,000 for college and coding`.
   - The Dispatcher agent handles the request, initiates parallel research across providers, and streams status updates and approval cards.
