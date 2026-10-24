"""Real Fetch.ai Orchestrator uAgent with Agent Chat Protocol (ACP v0.3.0)."""
import os
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4

# Ensure project root in sys.path
BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from dotenv import load_dotenv
from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    MetadataContent,
    StartSessionContent,
    TextContent,
    chat_protocol_spec
)

from backend.protocols.acp_integration import ACPIntegrationService
from backend.services.workflow_service import workflow_service

load_dotenv()

# Read configuration from environment
AGENT_NAME = os.getenv("AGENT_NAME", "dynamic_webmcp_operator")
AGENT_PORT = int(os.getenv("AGENT_PORT", "8001"))
AGENT_SEED = os.getenv("AGENT_SEED_PHRASE", "")
USE_MAILBOX = os.getenv("USE_AGENTVERSE", "true").lower() in ("true", "1", "yes")

if not AGENT_SEED:
    # Generate ephemeral fallback if not provided in environment for testing
    import secrets
    AGENT_SEED = f"ephemeral-seed-{secrets.token_hex(16)}"
    print("[WARNING] AGENT_SEED_PHRASE not set in .env. Generated temporary local seed.")

# Initialize the official Fetch.ai uAgent
agent = Agent(
    name=AGENT_NAME,
    seed=AGENT_SEED,
    port=AGENT_PORT,
    mailbox=USE_MAILBOX,
    publish_agent_details=True
)

# Instantiate the official Agent Chat Protocol
chat_proto = Protocol(spec=chat_protocol_spec)

# Message deduplication cache (LRU max 1000)
_seen_msgs: OrderedDict[str, bool] = OrderedDict()
MAX_SEEN = 1000


def make_chat_msg(
    text: str,
    end_session: bool = False,
    metadata_card: Optional[Dict[str, Any]] = None
) -> ChatMessage:
    """Helper to build ACP-compliant ChatMessage."""
    content: list[Any] = [TextContent(type="text", text=text)]
    if metadata_card:
        content.append(MetadataContent(type="metadata", metadata=metadata_card))
    if end_session:
        content.append(EndSessionContent(type="end-session"))
    return ChatMessage(
        timestamp=datetime.now(timezone.utc),
        msg_id=uuid4(),
        content=content
    )


@chat_proto.on_message(ChatMessage)
async def handle_incoming_chat(ctx: Context, sender: str, msg: ChatMessage):
    """Handle incoming messages from ASI:One conversation threads."""
    ctx.logger.info(f"Received message {msg.msg_id} from {sender}")

    # 1. Immediately acknowledge message receipt
    ack = ChatAcknowledgement(
        timestamp=datetime.now(timezone.utc),
        acknowledged_msg_id=msg.msg_id
    )
    await ctx.send(sender, ack)

    # 2. De-duplicate message IDs
    msg_str = str(msg.msg_id)
    if msg_str in _seen_msgs:
        ctx.logger.info(f"Ignoring duplicate message {msg_str}")
        return
    _seen_msgs[msg_str] = True
    if len(_seen_msgs) > MAX_SEEN:
        _seen_msgs.popitem(last=False)

    try:
        for item in msg.content:
            if isinstance(item, StartSessionContent):
                greeting = (
                    "👋 Hello! I am the **Dynamic WebMCP Agent Operator**.\n\n"
                    "I dynamically discover structured website tools across multiple retailers, "
                    "normalize their schemas, compare specs side-by-side, and request your explicit approval "
                    "before adding anything to your shopping cart.\n\n"
                    "💡 *Example: 'Find the best laptop under ₹70,000 for coding and college. Compare options and add the best to my cart. Do not check out.'*"
                )
                await ctx.send(sender, make_chat_msg(greeting))

            elif isinstance(item, TextContent):
                text = item.text.strip()
                if not text:
                    continue

                reply_msg = await process_user_text(ctx, sender, text)
                await ctx.send(sender, reply_msg)

            elif isinstance(item, EndSessionContent):
                ctx.logger.info(f"Session closed by {sender}")

    except Exception as e:
        ctx.logger.exception("Error in chat handler")
        err_msg = (
            "⚠️ An error occurred while processing your request. "
            "Please try rephrasing your goal, or say 'search again'. "
            "(No changes were made to any cart or account.)"
        )
        await ctx.send(sender, make_chat_msg(err_msg))


@chat_proto.on_message(ChatAcknowledgement)
async def handle_chat_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    ctx.logger.info(f"Delivery acknowledgement confirmed from {sender} for {msg.acknowledged_msg_id}")


async def process_user_text(ctx: Context, sender: str, text: str) -> ChatMessage:
    """Process natural language user requests and approval commands."""
    upper_text = text.upper()

    # Check for approval commands: "APPROVE <id>"
    if upper_text.startswith("APPROVE"):
        parts = text.split()
        if len(parts) >= 2:
            approval_id = parts[1].strip()
            try:
                result = workflow_service.execute_approved_action(
                    approval_id=approval_id,
                    sender_address=sender
                )
                cart_items = result.get("cart_state", {}).get("items", [])
                items_summary = f"{len(cart_items)} item(s) present" if cart_items else "Item verified"
                reply_text = (
                    f"✅ **Action Authorized and Verified!**\n\n"
                    f"• **Target Provider:** `{result['provider_id']}`\n"
                    f"• **Tool Invoked:** `{result['tool_name']}`\n"
                    f"• **Postcondition:** {result['verification_details']}\n"
                    f"• **Verified Cart State:** {items_summary}\n\n"
                    f"🛡️ *Checkout Boundary Safeguard:* Execution halted prior to checkout or payment."
                )
                return make_chat_msg(reply_text, end_session=False)
            except Exception as e:
                return make_chat_msg(f"❌ **Approval Execution Blocked:** {str(e)}")
        else:
            return make_chat_msg("⚠️ Please specify the approval token to authorize, e.g., `APPROVE appr_xxxx`.")

    # Check for rejection commands: "REJECT <id>" or "CANCEL <id>"
    elif upper_text.startswith("REJECT") or upper_text.startswith("CANCEL"):
        parts = text.split()
        if len(parts) >= 2:
            approval_id = parts[1].strip()
            try:
                res = workflow_service.cancel_approval(approval_id=approval_id, sender_address=sender)
                return make_chat_msg(f"🚫 **Action Cancelled:** {res['message']}")
            except Exception as e:
                return make_chat_msg(f"⚠️ Could not cancel approval: {str(e)}")
        else:
            return make_chat_msg("⚠️ Please specify the approval token to reject, e.g., `REJECT appr_xxxx`.")

    # General Shopping Goal Request
    # Execute unified workflow service
    task_res = workflow_service.run_search_and_compare(
        prompt=text,
        session_id=f"asi1_{sender[-8:] if len(sender) >= 8 else sender}",
        sender_address=sender
    )

    if task_res.get("status") == "NO_RESULTS":
        return make_chat_msg(f"🔍 {task_res['message']}")

    candidates = task_res.get("candidates", [])
    top = task_res.get("top_recommendation")
    rationale = task_res.get("routing_rationale", "")
    approval = task_res.get("approval_request")

    # Format compact comparison table for chat
    table_lines = [
        "| Option | Provider | Specs | Price |",
        "| :--- | :--- | :--- | :--- |"
    ]
    for c in candidates[:3]:
        specs = c.get("specs", {})
        spec_summary = f"{specs.get('cpu', 'N/A')} • {specs.get('ram', 'N/A')} • {specs.get('battery', 'N/A')}"
        is_top = "⭐ " if (top and c.get("sku") == top.get("sku")) else ""
        table_lines.append(f"| {is_top}**{c.get('title')}** | `{c.get('provider_id')}` | {spec_summary} | ₹{Number(c.get('price', 0)):,.0f} |")

    table_text = "\n".join(table_lines)

    response_text = (
        f"🎯 **Product Comparison & Decision Matrix**\n\n"
        f"{table_text}\n\n"
        f"💡 **Trade-off Analysis:**\n{rationale}\n\n"
    )

    if approval:
        response_text += (
            f"---\n"
            f"🛡️ **Action Authorization Required:**\n"
            f"I propose to add **{top.get('title')}** to your cart on **`{approval['provider_id']}`** "
            f"at **₹{approval['bound_price']:,.2f}**.\n\n"
            f"👉 To proceed, reply:\n"
            f"**`APPROVE {approval['approval_id']}`**\n\n"
            f"👉 To cancel, reply:\n"
            f"**`REJECT {approval['approval_id']}`**\n\n"
            f"*(Token valid for 5 minutes • Will strictly NOT check out)*"
        )

    # Attach interactive card metadata for ASI:One
    card_metadata = None
    if approval and top:
        card_metadata = {
            "type": "review_card",
            "title": "Authorize Cart Addition",
            "provider": approval["provider_id"],
            "product_title": top.get("title"),
            "price": f"₹{approval['bound_price']:,.2f}",
            "approval_id": approval["approval_id"],
            "expires_in": "300s"
        }

    return make_chat_msg(response_text, end_session=False, metadata_card=card_metadata)


def Number(val):
    try:
        return float(val)
    except Exception:
        return 0.0


# Include chat protocol in agent definition with manifest publishing
agent.include(chat_proto, publish_manifest=True)

if __name__ == "__main__":
    print("=================================================================")
    print(f"  Starting Fetch.ai uAgent: {agent.name}")
    print(f"  Agent Address: {agent.address}")
    print("=================================================================")
    agent.run()
