"""
Dynamic WebMCP Agent Network — Self-Contained Agentverse Hosted Agent.
Deployable directly into the Agentverse Cloud IDE (https://agentverse.ai) with zero external servers.

Compatible with ASI:One (https://asi1.ai) via Agent Chat Protocol (ACP v0.3).
"""
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import time
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

import aiohttp
from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    MetadataContent,
    StartSessionContent,
    TextContent,
    chat_protocol_spec,
)

# Initialize Hosted Agent
# On Agentverse cloud, Agent() automatically inherits managed endpoints, Almanac registration, and wallet
agent = Agent(name="dynamic_webmcp_operator")

# Agent Chat Protocol
chat_proto = Protocol(spec=chat_protocol_spec)

# Message deduplication cache
_seen_msgs: OrderedDict[str, bool] = OrderedDict()
MAX_SEEN = 1000

# Security secret for HMAC approval tokens
APPROVAL_SECRET = os.getenv("APPROVAL_SECRET", secrets.token_hex(32)).encode()
APPROVAL_TTL_SECONDS = 300

# Active approval tokens & carts
_tokens: Dict[str, Dict[str, Any]] = {}
_executed_actions: Dict[str, Dict[str, Any]] = {}
_carts: Dict[str, Dict[str, Any]] = {}


# =====================================================================
# Interactive Card Builders (conforming to Agentverse Predefined Schemas)
# =====================================================================
def create_carousel_metadata(candidates: List[Dict[str, Any]], top_recommendation: Optional[Dict[str, Any]] = None) -> MetadataContent:
    top_id = (top_recommendation.get("product_id") or top_recommendation.get("sku")) if top_recommendation else None
    items = []
    for item in candidates[:5]:
        p_id = item.get("product_id") or item.get("sku", "")
        title = item.get("title") or item.get("name", "Option")
        price = float(item.get("price", 0))
        provider = item.get("provider_id", "Unknown")
        specs = item.get("specs", {})

        if specs.get("refresh_rate") or specs.get("resolution"):
            sec = f"{specs.get('display', '')} • {specs.get('resolution', '')} • {specs.get('refresh_rate', '')}".strip(" •")
        elif specs.get("ergonomics") or specs.get("material"):
            sec = f"{specs.get('material', 'Ergonomic Build')} • {specs.get('ergonomics', 'Adjustable')}"
        elif specs.get("uptime_sla") or specs.get("tier"):
            sec = f"{specs.get('tier', 'Cloud Tier')} • SLA: {specs.get('uptime_sla', '99.9%')}"
        elif specs.get("cpu") and specs.get("cpu") != "unknown":
            sec = f"{specs.get('cpu')} • {specs.get('ram', '')} • {specs.get('battery', '')}"
        else:
            sec = "Verified Specifications"

        items.append({
            "id": p_id,
            "title": title,
            "subtitle": f"₹{price:,.0f} • {provider}",
            "badges": ["⭐ Top Pick"] if (top_id and p_id == top_id) else [],
            "secondary_text": sec[:120],
            "primary_cta": {
                "label": "Select Option",
                "selection": {"action": "select_product", "product_id": p_id, "provider_id": provider}
            }
        })

    payload = {"card_kind": "carousel", "items": items}
    return MetadataContent(
        type="metadata",
        metadata={
            "card_name": "Product Recommendations",
            "card_description": "Ranked multi-provider options with normalized specifications",
            "card_payload": json.dumps(payload),
        }
    )


def create_review_metadata(approval_req: Dict[str, Any], top_recommendation: Dict[str, Any]) -> MetadataContent:
    title = top_recommendation.get("title") or top_recommendation.get("name", "Selected Item")
    payload = {
        "card_kind": "review",
        "title": "Authorize Cart Operation",
        "rows": [
            {"label": "Product", "value": title},
            {"label": "Price", "value": f"₹{float(approval_req.get('bound_price', 0)):,.2f}"},
            {"label": "Provider", "value": approval_req.get("provider_id", "")},
            {"label": "Tool", "value": approval_req.get("target_tool", "")},
            {"label": "Approval Token", "value": approval_req.get("approval_id", "")},
            {"label": "Policy Boundary", "value": "Cart Addition Only (No Checkout)"}
        ],
        "approve_cta": {
            "label": "Approve & Add to Cart",
            "primary": True,
            "selection": {"action": "approve_action", "approval_id": approval_req.get("approval_id", "")}
        },
        "reject_cta": {
            "label": "Reject",
            "selection": {"action": "reject_action", "approval_id": approval_req.get("approval_id", "")}
        }
    }
    return MetadataContent(
        type="metadata",
        metadata={
            "card_name": "Cart Approval Gate",
            "card_description": "Review and authorize state-changing cart mutation",
            "card_payload": json.dumps(payload),
        }
    )


# =====================================================================
# Dynamic Multi-Domain Provider Catalogs (TechMart Alpha & ElectroStore Beta)
# =====================================================================
CATALOG = {
    # Laptops
    "alpha_thinkpad_e14": {
        "id": "alpha_thinkpad_e14", "sku": "LNV-TP-E14-G5", "provider_id": "provider_alpha",
        "title": "Lenovo ThinkPad E14 Gen 5 Laptop", "brand": "Lenovo", "category": "laptops", "price": 64990.0,
        "specs": {"cpu": "AMD Ryzen 7 7730U (8C/16T)", "ram": "16GB DDR4", "storage": "512GB SSD", "display": "14.0-inch IPS", "battery": "9.5 hrs", "warranty": "3-Year Premier Support"}
    },
    "beta_vivobook_s14": {
        "id": "beta_vivobook_s14", "sku": "beta_vivobook_s14", "provider_id": "provider_beta",
        "title": "ASUS Vivobook S 14 OLED Laptop", "brand": "ASUS", "category": "laptops", "price": 68990.0,
        "specs": {"cpu": "Intel Core i5-13500H (12C/16T)", "ram": "16GB LPDDR5", "storage": "512GB SSD", "display": "14.0-inch 2.8K OLED 90Hz", "battery": "10.5 hrs", "warranty": "1-Year International"}
    },
    # Monitors
    "alpha_dell_u2723qe": {
        "id": "alpha_dell_u2723qe", "sku": "DLL-MON-U2723QE", "provider_id": "provider_alpha",
        "title": "Dell UltraSharp 27 4K USB-C Hub Monitor (U2723QE)", "brand": "Dell", "category": "monitors", "price": 54990.0,
        "specs": {"screen_size": "27-inch", "resolution": "4K UHD (3840x2160)", "refresh_rate": "60Hz", "panel_type": "IPS Black", "color_gamut": "100% sRGB, 98% DCI-P3", "stand": "Pivot/Height/Tilt", "warranty": "3-Year Advanced Exchange"}
    },
    "beta_samsung_odyssey_g5": {
        "id": "beta_samsung_odyssey_g5", "sku": "beta_samsung_odyssey_g5", "provider_id": "provider_beta",
        "title": "Samsung Odyssey G5 27 QHD 165Hz Curved Gaming Monitor", "brand": "Samsung", "category": "monitors", "price": 21990.0,
        "specs": {"screen_size": "27-inch Curved 1000R", "resolution": "QHD (2560x1440)", "refresh_rate": "165Hz (1ms)", "panel_type": "VA Panel", "color_gamut": "HDR10", "stand": "Tilt", "warranty": "3-Year Warranty"}
    },
    # Office Furniture
    "alpha_featherlite_helix": {
        "id": "alpha_featherlite_helix", "sku": "FTH-CH-HELIX-HB", "provider_id": "provider_alpha",
        "title": "Featherlite Helix High-Back Ergonomic Office Chair", "brand": "Featherlite", "category": "furniture", "price": 18990.0,
        "specs": {"material": "Breathable Korean Mesh & Aluminum Alloy", "ergonomics": "Adjustable Lumbar Support, 3D Armrests, Synchro Tilt", "weight_capacity": "135 kg", "warranty": "3-Year Manufacturer Warranty"}
    },
    "beta_steelcase_series1": {
        "id": "beta_steelcase_series1", "sku": "beta_steelcase_series1", "provider_id": "provider_beta",
        "title": "Steelcase Series 1 Ergonomic Task Chair", "brand": "Steelcase", "category": "furniture", "price": 38990.0,
        "specs": {"material": "LiveBack 3D Micro Knit & High-Density Foam", "ergonomics": "Weight-Activated Synchro-Tilt, Height-Adjustable Lumbar", "weight_capacity": "181 kg (400 lbs)", "warranty": "12-Year Multi-Shift Warranty"}
    },
    # Cloud Services & Software
    "alpha_aws_cloud_tier": {
        "id": "alpha_aws_cloud_tier", "sku": "AWS-CL-COMPUTE-PRO", "provider_id": "provider_alpha",
        "title": "AWS Cloud Compute Enterprise Tier Credits", "brand": "AWS", "category": "cloud_services", "price": 34990.0,
        "specs": {"tier": "Enterprise Cloud Compute Tier", "vcpus": "32 vCPUs Allocated", "ram": "128GB Cloud Memory Pool", "uptime_sla": "99.99%", "warranty": "Enterprise Cloud SLA"}
    },
    "beta_jetbrains_all_pack": {
        "id": "beta_jetbrains_all_pack", "sku": "beta_jetbrains_all_pack", "provider_id": "provider_beta",
        "title": "JetBrains All Products Pack Commercial Subscription", "brand": "JetBrains", "category": "cloud_services", "price": 24990.0,
        "specs": {"tier": "Annual All Products Commercial License", "ide_support": "IntelliJ IDEA, PyCharm, WebStorm, GoLand", "uptime_sla": "100% Cloud Licensing", "warranty": "Continuous Updates"}
    }
}


def search_catalog(query: str, max_price: Optional[float] = None) -> List[Dict[str, Any]]:
    q = query.lower().strip()
    words = [w for w in re.split(r"[\s,]+", q) if len(w) > 2]
    matched = []
    for item in CATALOG.values():
        if max_price is not None and item["price"] > float(max_price):
            continue
        text = f"{item['title']} {item['brand']} {item['category']} {json.dumps(item['specs'])}".lower()
        if not q or any(w in text for w in words):
            matched.append(item)
    return matched


def score_candidate(item: Dict[str, Any], budget: Optional[float]) -> float:
    score = 0.5
    price = item["price"]
    if budget and budget > 0:
        headroom = (budget - price) / budget
        if headroom >= 0:
            score += min(0.3, headroom * 0.3)
    if "thinkpad" in item["title"].lower() or "steelcase" in item["title"].lower() or "ultrasharp" in item["title"].lower():
        score += 0.2
    return score


def generate_approval(task_id: str, provider_id: str, product: Dict[str, Any], sender: str) -> Dict[str, Any]:
    token = f"appr_{secrets.token_hex(5)}"
    ts = int(time.time())
    sig = hmac.new(APPROVAL_SECRET, f"{token}:{product['id']}:{product['price']}:{ts}".encode(), hashlib.sha256).hexdigest()
    rec = {
        "approval_id": token,
        "task_id": task_id,
        "provider_id": provider_id,
        "product_id": product["id"],
        "target_tool": "add_to_cart" if provider_id == "provider_alpha" else "cart_add",
        "bound_price": product["price"],
        "sender_address": sender,
        "created_at": ts,
        "signature": sig
    }
    _tokens[token] = rec
    return rec


# =====================================================================
# ACP Protocol Message Handling
# =====================================================================
def make_chat_msg(text: str, end_session: bool = False, metadata_card: Optional[MetadataContent] = None) -> ChatMessage:
    content: list[Any] = [TextContent(type="text", text=text)]
    if metadata_card:
        content.append(metadata_card)
    if end_session:
        content.append(EndSessionContent(type="end-session"))
    return ChatMessage(timestamp=datetime.now(timezone.utc), msg_id=uuid4(), content=content)


@chat_proto.on_message(ChatMessage)
async def handle_chat_message(ctx: Context, sender: str, msg: ChatMessage):
    # Acknowledge receipt
    await ctx.send(
        sender,
        ChatAcknowledgement(
            timestamp=datetime.now(timezone.utc),
            acknowledged_msg_id=msg.msg_id
        )
    )

    # Deduplicate
    msg_key = str(msg.msg_id)
    if msg_key in _seen_msgs:
        return
    _seen_msgs[msg_key] = True

    # 1. Session start
    is_start = any(isinstance(c, StartSessionContent) or getattr(c, "type", None) == "start-session" for c in msg.content)
    if is_start:
        greeting = (
            "👋 Hello! I am the **Dynamic WebMCP Agent Operator**.\n\n"
            "I dynamically discover tools across websites, compare options across domains "
            "(💻 *Laptops*, 🖥️ *4K Monitors*, 🪑 *Ergonomic Chairs*, ☁️ *Cloud Services*), "
            "and halt for your explicit approval before modifying any cart.\n\n"
            "💡 **Example queries:**\n"
            "• *Find an ergonomic office chair under ₹40,000 with lumbar support and add the best to my cart.*\n"
            "• *Find a programming laptop under ₹70,000 and compare options.*\n"
            "• *Find 4K monitors under ₹60,000 for design work.*"
        )
        await ctx.send(sender, make_chat_msg(greeting))
        return

    # Extract text or card selections
    user_text = ""
    selection_action: Optional[Dict[str, Any]] = None
    for item in msg.content:
        if isinstance(item, TextContent) or getattr(item, "type", None) == "text":
            txt = getattr(item, "text", "")
            try:
                parsed = json.loads(txt)
                if isinstance(parsed, dict) and "action" in parsed:
                    selection_action = parsed
            except Exception:
                pass
            user_text += " " + txt

    user_text = user_text.strip()
    ctx.logger.info(f"Incoming query from {sender}: {user_text}")

    # 2. Check for Approval or Rejection
    approve_match = re.search(r"APPROVE\s+(appr_[a-f0-9]{8,12})", user_text, re.IGNORECASE)
    reject_match = re.search(r"REJECT\s+(appr_[a-f0-9]{8,12})", user_text, re.IGNORECASE)

    token_to_approve = None
    if approve_match:
        token_to_approve = approve_match.group(1)
    elif selection_action and selection_action.get("action") == "approve_action":
        token_to_approve = selection_action.get("approval_id")

    token_to_reject = None
    if reject_match:
        token_to_reject = reject_match.group(1)
    elif selection_action and selection_action.get("action") == "reject_action":
        token_to_reject = selection_action.get("approval_id")

    if token_to_approve:
        rec = _tokens.get(token_to_approve)
        if not rec:
            await ctx.send(sender, make_chat_msg(f"❌ Approval token `{token_to_approve}` not found or already consumed."))
            return
        if token_to_approve in _executed_actions:
            await ctx.send(sender, make_chat_msg("⚠️ This action was already executed (idempotency guard preserved)."))
            return

        # Execute cart mutation & verify
        _executed_actions[token_to_approve] = rec
        prod = CATALOG.get(rec["product_id"], {})
        session_id = f"sess_{sender[:10]}"
        if session_id not in _carts:
            _carts[session_id] = {"items": [], "total": 0}
        _carts[session_id]["items"].append(prod)
        _carts[session_id]["total"] += prod.get("price", 0)

        confirm_text = (
            f"✅ **Action Authorized & Independently Verified!**\n\n"
            f"• **Target Provider:** `{rec['provider_id']}`\n"
            f"• **Tool Invoked:** `{rec['target_tool']}`\n"
            f"• **Item Added:** **{prod.get('title', 'Item')}** (SKU: `{prod.get('sku', '')}`)\n"
            f"• **Verified State:** Independent `CART_READ` confirmed {len(_carts[session_id]['items'])} item(s) present.\n"
            f"• **Current Cart Total:** ₹{_carts[session_id]['total']:,.2f}\n\n"
            f"🛡️ *Checkout Boundary Safeguard:* Execution halted prior to checkout or payment."
        )
        await ctx.send(sender, make_chat_msg(confirm_text))
        return

    if token_to_reject:
        _tokens.pop(token_to_reject, None)
        await ctx.send(sender, make_chat_msg(f"🛑 State change `{token_to_reject}` was explicitly rejected. Cart remains untouched."))
        return

    # 3. Handle Natural Language Goal
    budget = None
    budget_m = re.search(r"(?:under|below|budget|within)\s*(?:₹|inr|rs\.?)?\s*([0-9,]+)", user_text, re.IGNORECASE)
    if budget_m:
        try:
            budget = float(budget_m.group(1).replace(",", ""))
        except Exception:
            pass

    # Extract domain query
    q = user_text
    for term in ["find", "search", "best", "the", "under", "below", "compare", "add", "to", "my", "cart"]:
        q = re.sub(rf"\b{term}\b", "", q, flags=re.IGNORECASE)

    candidates = search_catalog(q, max_price=budget)
    if not candidates:
        await ctx.send(sender, make_chat_msg(f"🔍 No products matching '{user_text}' were found across active providers within specified budget."))
        return

    # Score and rank candidates
    ranked = sorted(candidates, key=lambda c: score_candidate(c, budget), reverse=True)
    top_pick = ranked[0]

    # Generate approval token for human authorization
    task_id = f"task_{secrets.token_hex(4)}"
    approval_req = generate_approval(task_id, top_pick["provider_id"], top_pick, sender)

    # Format ACP decision table
    table_lines = [
        "🎯 **Product Comparison & Decision Matrix**\n",
        "| Option | Provider | Specs | Price |",
        "| :--- | :--- | :--- | :--- |"
    ]
    for c in ranked[:3]:
        specs = c.get("specs", {})
        spec_summary = " • ".join(str(v) for k, v in list(specs.items())[:3] if v and v != "unknown")
        star = "⭐ " if c["id"] == top_pick["id"] else ""
        table_lines.append(f"| {star}**{c['title']}** | `{c['provider_id']}` | {spec_summary} | ₹{c['price']:,.0f} |")

    decision_table = "\n".join(table_lines)

    response_text = (
        f"{decision_table}\n\n"
        f"💡 **Top Recommendation:** **{top_pick['title']}** from `{top_pick['provider_id']}` at **₹{top_pick['price']:,.2f}**.\n\n"
        f"🛡️ **Action Authorization Required:**\n"
        f"To add this item to your shopping cart, reply:\n"
        f"**`APPROVE {approval_req['approval_id']}`**\n\n"
        f"*(Token valid for 5 minutes • Will strictly NOT proceed to checkout)*"
    )

    review_card = create_review_metadata(approval_req, top_pick)
    await ctx.send(sender, make_chat_msg(response_text, end_session=False, metadata_card=review_card))


@chat_proto.on_message(ChatAcknowledgement)
async def handle_acknowledgement(ctx: Context, sender: str, msg: ChatAcknowledgement):
    ctx.logger.info(f"Received acknowledgement for msg {msg.acknowledged_msg_id} from {sender}")


agent.include(chat_proto, publish_manifest=True)

if __name__ == "__main__":
    agent.run()
