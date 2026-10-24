"""Real Fetch.ai Orchestrator uAgent with Agent Chat Protocol (ACP)."""
import asyncio
import json
import os
import re
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4

# Load environment variables FIRST before importing any backend modules
from dotenv import load_dotenv
load_dotenv()

# Ensure project root in sys.path
BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

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

from backend.cards import (
    create_carousel_metadata,
    create_review_metadata
)
from backend.protocols.acp_integration import ACPIntegrationService
from backend.services.workflow_service import workflow_service

# Read configuration from environment
AGENT_NAME = os.getenv("AGENT_NAME", "dynamic_webmcp_operator")
AGENT_PORT = int(os.getenv("AGENT_PORT", "8001"))
AGENT_SEED = os.getenv("AGENT_SEED_PHRASE", "").strip()
USE_MAILBOX = os.getenv("USE_AGENTVERSE", "false").lower() in ("true", "1", "yes")


def validate_agent_config() -> bool:
    """Verify that agent has persistent seed when mailbox mode is enabled."""
    seed = os.getenv("AGENT_SEED_PHRASE", "").strip()
    mailbox_enabled = os.getenv("USE_AGENTVERSE", "false").lower() in ("true", "1", "yes")
    if mailbox_enabled and not seed:
        print("\n" + "=" * 70)
        print("❌ ERROR: AGENT_SEED_PHRASE is not set in your .env file!")
        print("When USE_AGENTVERSE=true (mailbox mode), an ephemeral seed would regenerate")
        print("a new agent address on every run, breaking your Agentverse Mailbox registration.")
        print("\n👉 Fix: Run `python scripts/gen_seed.py`, copy the 24 words, and set:")
        print('   AGENT_SEED_PHRASE="your 24 words here"')
        print("=" * 70 + "\n")
        return False
    return True


if not AGENT_SEED:
    import secrets
    AGENT_SEED = f"ephemeral-seed-{secrets.token_hex(16)}"
    if not USE_MAILBOX:
        print("[WARNING] AGENT_SEED_PHRASE not set in .env. Generated temporary local seed for offline test mode.")

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
    metadata_card: Optional[MetadataContent] = None
) -> ChatMessage:
    """Helper to build ACP-compliant ChatMessage."""
    content: list[Any] = [TextContent(type="text", text=text)]
    if metadata_card:
        content.append(metadata_card)
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


async def _execute_approval(ctx: Context, sender: str, approval_id: str) -> ChatMessage:
    try:
        result = await asyncio.to_thread(
            workflow_service.execute_approved_action,
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


async def _cancel_approval(ctx: Context, sender: str, approval_id: str) -> ChatMessage:
    try:
        res = await asyncio.to_thread(
            workflow_service.cancel_approval,
            approval_id=approval_id,
            sender_address=sender
        )
        return make_chat_msg(f"🚫 **Action Cancelled:** {res['message']}")
    except Exception as e:
        return make_chat_msg(f"⚠️ Could not cancel approval: {str(e)}")


async def process_user_text(ctx: Context, sender: str, text: str) -> ChatMessage:
    """Process natural language user requests, interactive card responses, and approval commands."""
    trimmed = text.strip()

    # 1. Handle JSON selections from Agentverse Interactive Card clicks
    card_data = None
    if trimmed.startswith("{") and trimmed.endswith("}"):
        try:
            parsed = json.loads(trimmed)
            if isinstance(parsed, dict) and "action" in parsed:
                card_data = parsed
        except Exception:
            card_data = None

    if card_data:
        action = str(card_data.get("action", "")).lower()
        approval_id = card_data.get("approval_id") or card_data.get("token") or card_data.get("id")
        if action in ("approve", "confirm") and approval_id:
            return await _execute_approval(ctx, sender, approval_id)
        elif action in ("reject", "cancel") and approval_id:
            return await _cancel_approval(ctx, sender, approval_id)
        elif action == "select_product":
            product_id = card_data.get("product_id")
            provider_id = card_data.get("provider_id")
            return make_chat_msg(f"Selected product `{product_id}` on `{provider_id}`. Would you like me to compare specs or add it to your cart?")

    # 2. Strict fullmatch for explicit approval/cancel text commands: APPROVE / REJECT / CANCEL <id>
    cmd_match = re.fullmatch(r"\s*(approve|reject|cancel)\s+(appr_[0-9a-f]+)\s*[.!]?\s*", text, re.I)
    if cmd_match:
        verb = cmd_match.group(1).lower()
        approval_id = cmd_match.group(2)
        if verb == "approve":
            return await _execute_approval(ctx, sender, approval_id)
        else:
            return await _cancel_approval(ctx, sender, approval_id)

    # 3. Regex search for conversational prose containing approval token (e.g., "Please approve appr_1234")
    token_match = re.search(r"\b(appr_[0-9a-f]+)\b", text, re.I)
    if token_match:
        approval_id = token_match.group(1)
        if re.search(r"\b(approve|yes|confirm|proceed|accept|go\s+ahead)\b", text, re.I):
            return await _execute_approval(ctx, sender, approval_id)
        elif re.search(r"\b(reject|no|cancel|deny|stop|abort)\b", text, re.I):
            return await _cancel_approval(ctx, sender, approval_id)

    # 4. General Shopping Goal Request
    # Send interim progress message so user and client know search is active
    try:
        await ctx.send(sender, make_chat_msg("🔎 Searching active providers and comparing candidate specifications..."))
    except Exception:
        pass

    try:
        task_res = await asyncio.wait_for(
            asyncio.to_thread(
                workflow_service.run_search_and_compare,
                prompt=text,
                session_id=f"asi1_{sender[-8:] if len(sender) >= 8 else sender}",
                sender_address=sender
            ),
            timeout=45.0
        )
    except asyncio.TimeoutError:
        return make_chat_msg("⏱️ The search operation timed out while querying remote providers. Please try asking with a narrower query or specific brand.")

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
        is_top = "⭐ " if (top and (c.get("sku") == top.get("sku") or c.get("product_id") == top.get("product_id"))) else ""
        c_title = c.get("title") or c.get("name", "Product")
        table_lines.append(f"| {is_top}**{c_title}** | `{c.get('provider_id')}` | {spec_summary} | ₹{Number(c.get('price', 0)):,.0f} |")

    table_text = "\n".join(table_lines)

    response_text = (
        f"🎯 **Product Comparison & Decision Matrix**\n\n"
        f"{table_text}\n\n"
        f"💡 **Trade-off Analysis:**\n{rationale}\n\n"
    )

    if approval and top:
        top_title = top.get("title") or top.get("name", "Item")
        response_text += (
            f"---\n"
            f"🛡️ **Action Authorization Required:**\n"
            f"I propose to add **{top_title}** to your cart on **`{approval['provider_id']}`** "
            f"at **₹{approval['bound_price']:,.2f}**.\n\n"
            f"👉 To proceed, reply:\n"
            f"**`APPROVE {approval['approval_id']}`**\n\n"
            f"👉 To cancel, reply:\n"
            f"**`REJECT {approval['approval_id']}`**\n\n"
            f"*(Token valid for 5 minutes • Will strictly NOT check out)*"
        )

    # Attach interactive card metadata for ASI:One / Agentverse
    card_metadata: Optional[MetadataContent] = None
    if approval and top:
        card_metadata = create_review_metadata(approval, top)
    elif candidates:
        card_metadata = create_carousel_metadata(candidates, top)

    return make_chat_msg(response_text, end_session=False, metadata_card=card_metadata)


def Number(val):
    try:
        return float(val)
    except Exception:
        return 0.0


# Include chat protocol in agent definition with manifest publishing
agent.include(chat_proto, publish_manifest=True)

if __name__ == "__main__":
    if not validate_agent_config():
        sys.exit(1)
    print("=================================================================")
    print(f"  Starting Fetch.ai uAgent: {agent.name}")
    print(f"  Agent Address: {agent.address}")
    print("  Agent Inspector: Open Agent Inspector on Agentverse to monitor live RPCs")
    print("=================================================================")
    agent.run()
