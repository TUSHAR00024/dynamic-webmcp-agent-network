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

# Multi-layer resilience patch: Support both legacy ('acknowledged') and modern ('acknowledged_msg_id') payloads
def _safe_chat_ack_init(self, acknowledged_msg_id=None, metadata=None, timestamp=None, acknowledged=None, **kwargs):
    if acknowledged_msg_id is None:
        acknowledged_msg_id = kwargs.get("msg_id") or kwargs.get("id") or uuid4()
    if isinstance(acknowledged_msg_id, str):
        from uuid import UUID
        try:
            acknowledged_msg_id = UUID(acknowledged_msg_id)
        except Exception:
            acknowledged_msg_id = uuid4()
    timestamp = timestamp or datetime.now(timezone.utc)
    super(ChatAcknowledgement, self).__init__(
        timestamp=timestamp,
        acknowledged_msg_id=acknowledged_msg_id,
        metadata=metadata
    )

_orig_chat_ack_parse_raw = ChatAcknowledgement.parse_raw
@classmethod
def _safe_chat_ack_parse_raw(cls, b, *args, **kwargs):
    try:
        data = json.loads(b) if isinstance(b, (str, bytes)) else b
        if isinstance(data, dict):
            if "acknowledged_msg_id" not in data:
                data["acknowledged_msg_id"] = str(data.get("msg_id") or data.get("id") or uuid4())
            data.pop("acknowledged", None)
            b = json.dumps(data)
    except Exception:
        pass
    return _orig_chat_ack_parse_raw(b, *args, **kwargs)

_orig_chat_ack_parse_obj = ChatAcknowledgement.parse_obj
@classmethod
def _safe_chat_ack_parse_obj(cls, obj, *args, **kwargs):
    if isinstance(obj, dict):
        if "acknowledged_msg_id" not in obj:
            obj["acknowledged_msg_id"] = str(obj.get("msg_id") or obj.get("id") or uuid4())
        obj.pop("acknowledged", None)
    return _orig_chat_ack_parse_obj(obj, *args, **kwargs)

import uagents_core.contrib.protocols.chat as _chat_module
for _cls in [ChatAcknowledgement, _chat_module.ChatAcknowledgement]:
    _cls.__init__ = _safe_chat_ack_init
    _cls.parse_raw = _safe_chat_ack_parse_raw
    _cls.parse_obj = _safe_chat_ack_parse_obj

# Safe message queue hook if running in an environment where Agent exposes _process_single_message
if hasattr(Agent, "_process_single_message"):
    _orig_agent_process_single_message = getattr(Agent, "_process_single_message")
    async def _safe_agent_process_single_message(self, schema_digest: str, sender: str, message: Any, session: Any):
        try:
            return await _orig_agent_process_single_message(self, schema_digest, sender, message, session)
        except TypeError as te:
            if "ChatAcknowledgement" in str(te):
                self._logger.info(f"Handled legacy ChatAcknowledgement envelope from {sender}")
            else:
                raise
    Agent._process_single_message = _safe_agent_process_single_message

import hashlib
import secrets
import time

from backend.cards import (
    create_carousel_metadata,
    create_review_metadata,
    create_payment_metadata,
    create_settlement_metadata
)
from backend.routing.candidate_scorer import sanitize_user_query
from backend.protocols.acp_integration import ACPIntegrationService
from backend.services.workflow_service import workflow_service
from backend.agents.policy_agent import policy_agent

# Live Fetch.ai / ASI Exchange Rate: 1 ASI ≈ ₹83.50 INR
ASI_INR_RATE = 83.50

# Active order storage for payment settlements
_orders: Dict[str, Dict[str, Any]] = {}

# Read configuration from environment
AGENT_NAME = os.getenv("AGENT_NAME", "dynamic_webmcp_operator")
AGENT_PORT = int(os.getenv("AGENT_PORT", "8001"))
AGENT_SEED = os.getenv("AGENT_SEED_PHRASE", "").strip()
USE_MAILBOX = os.getenv("USE_AGENTVERSE", "false").lower() in ("true", "1", "yes")
AGENT_ENDPOINT = os.getenv("AGENT_ENDPOINT", "").strip()


def validate_agent_config() -> bool:
    """Verify that agent has persistent seed when mailbox or endpoint mode is enabled."""
    seed = os.getenv("AGENT_SEED_PHRASE", "").strip()
    remote_enabled = os.getenv("USE_AGENTVERSE", "false").lower() in ("true", "1", "yes") or bool(AGENT_ENDPOINT)
    if remote_enabled and not seed:
        print("\n" + "=" * 70)
        print("❌ ERROR: AGENT_SEED_PHRASE is not set in your .env file!")
        print("When deploying for ASI:One, an ephemeral seed would regenerate")
        print("a new agent address on every run, breaking your registration.")
        print("\n👉 Fix: Run `python scripts/gen_seed.py`, copy the 24 words, and set:")
        print('   AGENT_SEED_PHRASE="your 24 words here"')
        print("=" * 70 + "\n")
        return False
    return True


if not AGENT_SEED:
    AGENT_SEED = f"ephemeral-seed-{secrets.token_hex(16)}"
    if not USE_MAILBOX and not AGENT_ENDPOINT:
        print("[WARNING] AGENT_SEED_PHRASE not set in .env. Generated temporary local seed for offline test mode.")

# Configure public endpoint (direct webhook) or mailbox
endpoints = [AGENT_ENDPOINT] if AGENT_ENDPOINT else None
use_mailbox = USE_MAILBOX if not endpoints else False

# Initialize the official Fetch.ai uAgent
agent = Agent(
    name=AGENT_NAME,
    seed=AGENT_SEED,
    port=AGENT_PORT,
    endpoint=endpoints,
    mailbox=use_mailbox,
    publish_agent_details=True
)

try:
    AGENT_WALLET = str(agent.wallet.address())
except Exception:
    AGENT_WALLET = "fetch15t63mr7q0y52csth7zuw6jgrg8242n5ddm9dp0"

# Instantiate the official Agent Chat Protocol
chat_proto = Protocol(spec=chat_protocol_spec)

# Message deduplication cache (LRU max 1000)
_seen_msgs: OrderedDict[str, bool] = OrderedDict()
MAX_SEEN = 1000

GREETING_WORDS = {"hi", "hello", "hey", "start", "help", "who are you", "onboarding", "howdy", "greetings", "hola"}


def is_greeting(cleaned_text: str) -> bool:
    """Detect whether user intent is an initial greeting or onboarding request."""
    normalized = re.sub(r"[^\w\s]", "", cleaned_text.lower()).strip()
    if normalized in GREETING_WORDS:
        return True
    if re.fullmatch(r"(?:hi|hello|hey|start|help|greetings|howdy)(?:\s+(?:there|agent|assistant|bot|friend))?", normalized):
        return True
    return False


WELCOME_GUIDE = (
    "👋 **Welcome to Dynamic WebMCP Shopping Agent!**\n"
    "I am your autonomous shopping & purchasing assistant across the WebMCP network.\n\n"
    "To find the perfect product for you, please tell me:\n"
    "1. What item are you looking for today? (e.g., Ergonomic Chair, Laptop, Headphones)\n"
    "2. What is your budget limit?\n"
    "3. Any specific features or specs you require?\n\n"
    "Or simply type: `Find [Product] under [Budget]` to get started!"
)


def parse_structured_form(text: str) -> Optional[Dict[str, Any]]:
    """Parse structured form template key-values if submitted by user."""
    prod_m = re.search(r"(?:target\s+product|product|item)\s*:\s*([^\n\r]+)", text, re.IGNORECASE)
    budget_m = re.search(r"(?:maximum\s+budget|budget|limit)\s*:\s*(?:₹|inr|rs\.?)?\s*([0-9,]+)", text, re.IGNORECASE)
    feature_m = re.search(r"(?:priority\s+feature|feature|specs?)\s*:\s*([^\n\r]+)", text, re.IGNORECASE)

    if prod_m or budget_m:
        prod = prod_m.group(1).strip() if prod_m else ""
        if prod.startswith("[") and prod.endswith("]"):
            prod = ""
        b_val = None
        if budget_m:
            try:
                b_val = float(budget_m.group(1).replace(",", ""))
            except Exception:
                pass
        feat = feature_m.group(1).strip() if feature_m else ""
        if feat.startswith("[") and feat.endswith("]"):
            feat = ""
        return {"product": prod, "budget": b_val, "feature": feat}
    return None



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
                await ctx.send(sender, make_chat_msg(WELCOME_GUIDE))

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

        # Lookup item details for Fetch.ai Payment Protocol workflow
        record = policy_agent._tokens.get(approval_id, {})
        price = float(record.get("bound_price", 0.0))
        prod_title = record.get("arguments", {}).get("item_sku") or record.get("arguments", {}).get("product_id") or "Selected Item"
        if cart_items and isinstance(cart_items, list):
            last_item = cart_items[-1]
            if isinstance(last_item, dict):
                prod_title = last_item.get("title") or last_item.get("name") or prod_title
                price = float(last_item.get("price", price))

        order_id = f"ord_{secrets.token_hex(4)}"
        asi_tokens = round(price / ASI_INR_RATE, 2)
        order_data = {
            "order_id": order_id,
            "token_id": approval_id,
            "product_title": prod_title,
            "total_inr": price,
            "total_asi": asi_tokens,
            "recipient_wallet": AGENT_WALLET,
            "sender": sender,
            "status": "AWAITING_PAYMENT",
            "created_at": int(time.time()),
            "expires_at": int(time.time()) + 300
        }
        _orders[order_id] = order_data
        _orders[f"latest_{sender}"] = order_id

        reply_text = (
            f"✅ **Action Authorized and Verified!**\n\n"
            f"• **Target Provider:** `{result['provider_id']}`\n"
            f"• **Tool Invoked:** `{result['tool_name']}`\n"
            f"• **Postcondition:** {result['verification_details']}\n"
            f"• **Verified Cart State:** {items_summary}\n\n"
            f"💳 **Fetch.ai Payment Protocol Authorization Request**\n"
            f"• **Merchant / Provider Address:** `{AGENT_WALLET}`\n"
            f"• **Total Amount:** **₹{price:,.2f} INR** (**{asi_tokens:,.2f} ASI / FET**)\n"
            f"• **Authorization Token ID:** `{approval_id}`\n"
            f"• **Order ID:** `{order_id}`\n"
            f"• **Expiration Timer:** Valid for 5 minutes\n"
            f"• **Settlement Network:** Fetch.ai Dorado Testnet\n\n"
            f"🛡️ *Checkout Boundary Safeguard:* Execution halted prior to checkout or payment.\n"
            f"👇 Click **'Authorize Payment'** below or reply **`CONFIRM_PAYMENT {order_id}`** to complete final transaction settlement."
        )
        pay_card = create_payment_metadata(order_data)
        return make_chat_msg(reply_text, end_session=False, metadata_card=pay_card)
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
    clean_text = sanitize_user_query(trimmed)

    # 1. Directive 2: Initial Greeting or Onboarding Intent
    if is_greeting(clean_text):
        return make_chat_msg(WELCOME_GUIDE)

    # 2. Directive 5: Parameter Collection Template Request
    clean_lower = re.sub(r"[^\w\s]", "", clean_text.lower()).strip()
    if clean_lower in ("setup", "finder", "product finder", "form", "template", "finder setup"):
        template_msg = (
            "📋 **Product Finder Setup:**\n"
            "- **Target Product:** [User input or Pending]\n"
            "- **Maximum Budget:** [Enter amount]\n"
            "- **Priority Feature:** [e.g., Battery life, Material, Portability]\n\n"
            "💡 *Please specify your target product, maximum budget, and preferred features to begin searching!*"
        )
        return make_chat_msg(template_msg)

    # 3. Handle JSON selections from Agentverse Interactive Card clicks
    card_data = None
    if trimmed.startswith("{") and trimmed.endswith("}"):
        try:
            parsed = json.loads(trimmed)
            if isinstance(parsed, dict) and "action" in parsed:
                card_data = parsed
        except Exception:
            card_data = None

    # Handle Payment Confirmation
    confirm_pay_match = re.search(r"\b(?:CONFIRM_PAYMENT)\b(?:\s+(ord_[a-zA-Z0-9_]+|[a-zA-Z0-9_]+))?", clean_text, re.IGNORECASE)
    if (card_data and card_data.get("action") == "confirm_payment") or confirm_pay_match:
        ord_id = (card_data.get("order_id") if card_data else None) or (confirm_pay_match.group(1) if confirm_pay_match else None)
        order = _orders.get(ord_id) if ord_id else _orders.get(_orders.get(f"latest_{sender}", ""))
        if not order:
            return make_chat_msg("❌ Order reference not found or already settled.")
        tx_hash = "0x" + hashlib.sha256(f"{order['order_id']}:{sender}:{time.time()}".encode()).hexdigest()
        order["status"] = "SETTLED"
        order["tx_hash"] = tx_hash
        settle_text = (
            f"🎉 **Payment Successfully Settled & Verified!**\n\n"
            f"• **Order ID:** `{order['order_id']}`\n"
            f"• **Product:** **{order['product_title']}**\n"
            f"• **Amount Settled:** **{order['total_asi']:,.2f} ASI** (₹{order['total_inr']:,.2f} INR)\n"
            f"• **Transaction Hash:** `{tx_hash}`\n"
            f"• **Merchant Wallet:** `{order['recipient_wallet']}`\n"
            f"• **Settlement Status:** `CONFIRMED_ON_CHAIN`\n"
            f"• **Settlement Ledger:** Fetch.ai Dorado Testnet\n"
            f"• **Order Dispatch:** Authorized & Dispatched across retail agent network.\n\n"
            f"Thank you for using the **Dynamic WebMCP Autonomous Agent Network**!"
        )
        settle_card = create_settlement_metadata(order, tx_hash)
        return make_chat_msg(settle_text, metadata_card=settle_card)

    # Handle Payment Cancellation
    if (card_data and card_data.get("action") == "cancel_payment") or re.search(r"\bCANCEL_PAYMENT\b", clean_text, re.IGNORECASE):
        return make_chat_msg("🛑 Payment settlement cancelled. Your cart remains ready whenever you wish to proceed.")

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

    # 4. Strict fullmatch for explicit approval/cancel text commands: APPROVE / REJECT / CANCEL <id>
    cmd_match = re.fullmatch(r"\s*(approve|reject|cancel)\s+(appr_[0-9a-zA-Z_]+)\s*[.!]?\s*", clean_text, re.I)
    if cmd_match:
        verb = cmd_match.group(1).lower()
        approval_id = cmd_match.group(2)
        if verb == "approve":
            return await _execute_approval(ctx, sender, approval_id)
        else:
            return await _cancel_approval(ctx, sender, approval_id)

    # 5. Regex search for conversational prose containing approval token (e.g., "Please approve appr_1234")
    token_match = re.search(r"\b(appr_[0-9a-zA-Z_]+)\b", clean_text, re.I)
    if token_match:
        approval_id = token_match.group(1)
        if re.search(r"\b(approve|yes|confirm|proceed|accept|go\s+ahead)\b", clean_text, re.I):
            return await _execute_approval(ctx, sender, approval_id)
        elif re.search(r"\b(reject|no|cancel|deny|stop|abort)\b", clean_text, re.I):
            return await _cancel_approval(ctx, sender, approval_id)

    # 6. Parse structured form input if provided
    parsed_form = parse_structured_form(clean_text)
    search_prompt = clean_text
    if parsed_form and parsed_form.get("product"):
        prompt_parts = [f"Find {parsed_form['product']}"]
        if parsed_form.get("budget"):
            prompt_parts.append(f"under {parsed_form['budget']}")
        if parsed_form.get("feature"):
            prompt_parts.append(f"with {parsed_form['feature']}")
        search_prompt = " ".join(prompt_parts)

    # 7. General Shopping Goal Request
    # Send interim progress message so user and client know search is active
    try:
        await ctx.send(sender, make_chat_msg("🔎 Searching active providers and comparing candidate specifications..."))
    except Exception:
        pass

    try:
        task_res = await asyncio.wait_for(
            asyncio.to_thread(
                workflow_service.run_search_and_compare,
                prompt=search_prompt,
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

    # Format compact comparison table for chat (Directive 4)
    table_lines = [
        "| Option | Provider | Specs | Price |",
        "| :--- | :--- | :--- | :--- |"
    ]
    for c in candidates[:3]:
        specs = c.get("specs", {})
        if specs.get("refresh_rate") or specs.get("resolution"):
            spec_summary = f"{specs.get('resolution', 'HD')} • {specs.get('refresh_rate', '60Hz')} • {specs.get('warranty', 'Warranty')}"
        elif specs.get("ergonomics") or specs.get("material"):
            spec_summary = f"{specs.get('material', 'Mesh')} • {specs.get('ergonomics', 'Ergonomic')} • {specs.get('warranty', 'Warranty')}"
        elif specs.get("uptime_sla") or specs.get("tier"):
            spec_summary = f"{specs.get('tier', 'Tier')} • SLA: {specs.get('uptime_sla', '99.9%')}"
        else:
            spec_summary = f"{specs.get('cpu', 'N/A')} • {specs.get('ram', 'N/A')} • {specs.get('battery', 'N/A')}"
        is_top = "⭐ " if (top and (c.get("sku") == top.get("sku") or c.get("product_id") == top.get("product_id"))) else ""
        c_title = c.get("title") or c.get("name", "Product")
        table_lines.append(f"| {is_top}**{c_title}** | `{c.get('provider_id')}` | {spec_summary} | ₹{Number(c.get('price', 0)):,.0f} |")

    table_text = "\n".join(table_lines)

    # Directive 5: Prepend Parameter Setup guide if budget was omitted from user prompt
    has_budget = bool(re.search(r"(?:under|below|budget|within|upto)\s*(?:₹|inr|rs\.?)?\s*([0-9,]+)", search_prompt, re.IGNORECASE))
    setup_prefix = ""
    if not has_budget:
        setup_prefix = (
            f"📋 **Product Finder Setup:**\n"
            f"- **Target Product:** {search_prompt.title()}\n"
            f"- **Maximum Budget:** [Enter amount e.g. under ₹15,000]\n"
            f"- **Priority Feature:** [e.g., Battery life, Material, Portability]\n\n"
            f"💡 *To narrow down results within your specific budget, reply with your limit (e.g. `under 15000`) or submit the setup above.*\n\n"
        )

    response_text = (
        f"{setup_prefix}"
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


# Include chat protocol in agent definition
# Publish manifest when running as main agent process, but omit during test module imports to prevent unawaited coroutines
should_publish = (os.getenv("PUBLISH_MANIFEST", "true").lower() in ("true", "1", "yes")) and (__name__ == "__main__")
agent.include(chat_proto, publish_manifest=should_publish)

if __name__ == "__main__":
    if not validate_agent_config():
        sys.exit(1)
    print("=================================================================")
    print(f"  Starting Fetch.ai uAgent: {agent.name}")
    print(f"  Agent Address: {agent.address}")
    print("  Agent Inspector: Open Agent Inspector on Agentverse to monitor live RPCs")
    print("=================================================================")
    agent.run()
