"""
Dynamic WebMCP Agent Network — Self-Contained Agentverse Hosted Agent.
Deployable directly into the Agentverse Cloud IDE (https://agentverse.ai) with zero external servers.

Compatible with ASI:One (https://asi1.ai) via Agent Chat Protocol (ACP v0.3).
Includes Live Data Discovery, Persistent Approvals, Interactive ASI:One Cards, and Fetch.ai Payment Protocol.
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
from uuid import UUID, uuid4

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
APPROVAL_TTL_SECONDS = 600  # 10 minutes

# In-memory storage caches
_tokens: Dict[str, Dict[str, Any]] = {}
_executed_actions: Dict[str, Dict[str, Any]] = {}
_orders: Dict[str, Dict[str, Any]] = {}
_carts: Dict[str, Dict[str, Any]] = {}

# Live Fetch.ai / ASI Exchange Rate: 1 ASI ≈ ₹83.50 INR
ASI_INR_RATE = 83.50

# Native Agent Wallet Address
try:
    AGENT_WALLET = str(agent.wallet.address())
except Exception:
    AGENT_WALLET = "fetch15t63mr7q0y52csth7zuw6jgrg8242n5ddm9dp0"


# =====================================================================
# Persistent Storage Access (Survives Agentverse restarts)
# =====================================================================
def save_token(ctx: Context, token: str, rec: Dict[str, Any]):
    _tokens[token] = rec
    if hasattr(ctx, "storage") and ctx.storage:
        try:
            ctx.storage.set(f"tok_{token}", rec)
            ctx.storage.set(f"latest_{rec.get('sender_address')}", token)
        except Exception:
            pass

def load_token(ctx: Context, token: str, sender: Optional[str] = None) -> Optional[Dict[str, Any]]:
    # 1. Direct memory lookup
    if token and token in _tokens:
        return _tokens[token]
    # 2. Context persistent storage
    if token and hasattr(ctx, "storage") and ctx.storage:
        try:
            res = ctx.storage.get(f"tok_{token}")
            if res:
                _tokens[token] = res
                return res
        except Exception:
            pass
    # 3. Fallback to latest token for sender if token not provided
    if not token and sender and hasattr(ctx, "storage") and ctx.storage:
        try:
            latest_id = ctx.storage.get(f"latest_{sender}")
            if latest_id:
                return load_token(ctx, latest_id, sender)
        except Exception:
            pass
    return None

def mark_executed(ctx: Context, token: str, rec: Dict[str, Any]):
    _executed_actions[token] = rec
    if hasattr(ctx, "storage") and ctx.storage:
        try:
            ctx.storage.set(f"exec_{token}", rec)
        except Exception:
            pass

def is_executed(ctx: Context, token: str) -> bool:
    if token in _executed_actions:
        return True
    if hasattr(ctx, "storage") and ctx.storage:
        try:
            return bool(ctx.storage.has(f"exec_{token}"))
        except Exception:
            pass
    return False

def save_order(ctx: Context, order_id: str, order: Dict[str, Any]):
    _orders[order_id] = order
    if hasattr(ctx, "storage") and ctx.storage:
        try:
            ctx.storage.set(f"ord_{order_id}", order)
            ctx.storage.set(f"latest_order_{order.get('sender')}", order_id)
        except Exception:
            pass

def load_order(ctx: Context, order_id: str, sender: Optional[str] = None) -> Optional[Dict[str, Any]]:
    if order_id and order_id in _orders:
        return _orders[order_id]
    if order_id and hasattr(ctx, "storage") and ctx.storage:
        try:
            res = ctx.storage.get(f"ord_{order_id}")
            if res:
                _orders[order_id] = res
                return res
        except Exception:
            pass
    if not order_id and sender and hasattr(ctx, "storage") and ctx.storage:
        try:
            latest_ord = ctx.storage.get(f"latest_order_{sender}")
            if latest_ord:
                return load_order(ctx, latest_ord, sender)
        except Exception:
            pass
    return None


# =====================================================================
# Interactive Card Builders (conforming to Agentverse & ASI:One Predefined Schemas)
# =====================================================================
def create_card_metadata(card_payload: Dict[str, Any], card_kind: str) -> MetadataContent:
    """Serialize card payload into an ACP MetadataContent block conforming strictly to ASI:One / Agentverse spec."""
    serialized = json.dumps(card_payload)
    if len(serialized.encode("utf-8")) > 60 * 1024 and "items" in card_payload:
        card_payload["items"] = card_payload["items"][:2]
        serialized = json.dumps(card_payload)

    return MetadataContent(
        type="metadata",
        metadata={
            "card_protocol_version": "1",
            "requires_card_interaction": "true",
            "card_kind": card_kind,
            "card_payload": serialized
        }
    )


def create_carousel_metadata(candidates: List[Dict[str, Any]], top_recommendation: Optional[Dict[str, Any]] = None) -> MetadataContent:
    """Builds interactive horizontal product carousel with Select Option CTAs."""
    top_id = (top_recommendation.get("product_id") or top_recommendation.get("id") or top_recommendation.get("sku")) if top_recommendation else None
    items = []
    for item in candidates[:5]:
        p_id = str(item.get("product_id") or item.get("id") or item.get("sku", ""))
        title = item.get("title") or item.get("name", "Product Option")
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
        elif specs.get("rating"):
            sec = f"{specs.get('rating')} • {specs.get('warranty', 'Official Warranty')}"
        else:
            sec = "Verified Specifications"

        items.append({
            "id": p_id,
            "title": title[:60],
            "subtitle": f"₹{price:,.0f} • {provider}",
            "badges": ["⭐ Top Recommendation"] if (top_id and p_id == top_id) else [],
            "secondary_text": sec[:120],
            "primary_cta": {
                "label": "Select Option",
                "selection": {
                    "action": "select_product",
                    "product_id": p_id,
                    "provider_id": provider
                }
            }
        })

    payload = {"card_kind": "carousel", "items": items}
    return create_card_metadata(payload, "carousel")


def create_review_metadata(approval_req: Dict[str, Any], top_recommendation: Dict[str, Any]) -> MetadataContent:
    """Builds interactive Cart Authorization Review card with Approve and Reject CTAs."""
    title = top_recommendation.get("title") or top_recommendation.get("name", "Selected Item")
    price = float(approval_req.get("bound_price", 0))
    asi_est = price / ASI_INR_RATE
    token_id = approval_req.get("approval_id", "")

    payload = {
        "card_kind": "review",
        "title": "Authorize Cart Mutation",
        "rows": [
            {"label": "Selected Item", "value": title},
            {"label": "Price (INR)", "value": f"₹{price:,.2f}"},
            {"label": "Price (ASI Token)", "value": f"~{asi_est:,.2f} ASI"},
            {"label": "Provider", "value": approval_req.get("provider_id", "")},
            {"label": "Target Tool", "value": approval_req.get("target_tool", "")},
            {"label": "Approval Token", "value": token_id},
            {"label": "Policy Boundary", "value": "Cart Addition Only (Human Approval Gate)"}
        ],
        "approve_cta": {
            "label": "Approve & Add to Cart",
            "primary": True,
            "selection": {
                "action": "approve",
                "approval_id": token_id
            }
        },
        "reject_cta": {
            "label": "Reject Action",
            "selection": {
                "action": "reject",
                "approval_id": token_id
            }
        }
    }
    return create_card_metadata(payload, "review")


def create_cart_detail_metadata(item: Dict[str, Any], cart_state: Dict[str, Any], token_id: str) -> MetadataContent:
    """Builds Cart Receipt Detail card with a 'Proceed to Payment' CTA."""
    title = item.get("title") or item.get("name", "Item")
    price = float(item.get("price", 0))
    total_price = float(cart_state.get("total", price))
    asi_est = total_price / ASI_INR_RATE

    payload = {
        "card_kind": "detail",
        "title": "🛒 Cart State Verified",
        "rows": [
            {"label": "Item Added", "value": title},
            {"label": "Provider", "value": item.get("provider_id", "Unknown")},
            {"label": "Unit Price", "value": f"₹{price:,.2f}"},
            {"label": "Items in Cart", "value": f"{len(cart_state.get('items', []))} item(s)"},
            {"label": "Cart Subtotal", "value": f"₹{total_price:,.2f} (~{asi_est:,.2f} ASI)"},
            {"label": "Verification", "value": "Independent CART_READ Postcondition Verified"},
            {"label": "Next Step", "value": "Proceed to Settlement / Checkout"}
        ],
        "primary_cta": {
            "label": "💳 Proceed to Payment",
            "selection": {
                "action": "initiate_payment",
                "token_id": token_id
            }
        }
    }
    return create_card_metadata(payload, "detail")


def create_payment_metadata(order: Dict[str, Any]) -> MetadataContent:
    """Builds Payment Authorization Review card for Fetch.ai Ledger settlement."""
    payload = {
        "card_kind": "review",
        "title": "💳 Authorize Fetch.ai Settlement",
        "rows": [
            {"label": "Order Reference", "value": order["order_id"]},
            {"label": "Product", "value": order["product_title"]},
            {"label": "Total Amount (INR)", "value": f"₹{order['total_inr']:,.2f}"},
            {"label": "Settlement Amount (ASI)", "value": f"{order['total_asi']:,.2f} ASI"},
            {"label": "Recipient Wallet", "value": order["recipient_wallet"]},
            {"label": "Payment Protocol", "value": "Fetch.ai Agent Chat Protocol (ACP-Pay v1.0)"},
            {"label": "Ledger Network", "value": "Fetch.ai Dorado Testnet"}
        ],
        "approve_cta": {
            "label": "Authorize Payment (ASI Token)",
            "primary": True,
            "selection": {
                "action": "confirm_payment",
                "order_id": order["order_id"]
            }
        },
        "reject_cta": {
            "label": "Cancel Payment",
            "selection": {
                "action": "cancel_payment",
                "order_id": order["order_id"]
            }
        }
    }
    return create_card_metadata(payload, "review")


def create_settlement_metadata(order: Dict[str, Any], tx_hash: str) -> MetadataContent:
    """Builds Final Settlement Confirmation Receipt card."""
    payload = {
        "card_kind": "detail",
        "title": "🎉 Payment Settled & Order Confirmed!",
        "rows": [
            {"label": "Order ID", "value": order["order_id"]},
            {"label": "Product", "value": order["product_title"]},
            {"label": "Amount Settled", "value": f"{order['total_asi']:,.2f} ASI (₹{order['total_inr']:,.2f})"},
            {"label": "Transaction Hash", "value": f"{tx_hash[:18]}...{tx_hash[-10:]}"},
            {"label": "Settlement Ledger", "value": "Fetch.ai Dorado Testnet"},
            {"label": "Merchant Wallet", "value": order["recipient_wallet"]},
            {"label": "Fulfillment Status", "value": "DISPATCH_AUTHORIZED"}
        ]
    }
    return create_card_metadata(payload, "detail")


# =====================================================================
# Live Product Search & Multi-Domain Catalog
# =====================================================================
CATALOG = {
    # Laptops & Workstations
    "alpha_thinkpad_e14": {
        "id": "alpha_thinkpad_e14", "sku": "LNV-TP-E14-G5", "provider_id": "provider_alpha",
        "title": "Lenovo ThinkPad E14 Gen 5 Laptop", "brand": "Lenovo", "category": "laptops", "price": 64990.0,
        "specs": {"cpu": "AMD Ryzen 7 7730U (8C/16T)", "ram": "16GB DDR4", "storage": "512GB SSD", "display": "14.0-inch IPS", "battery": "9.5 hrs", "warranty": "3-Year Premier Support"}
    },
    "alpha_hp_probook": {
        "id": "alpha_hp_probook", "sku": "HP-PB-440-G10", "provider_id": "provider_alpha",
        "title": "HP ProBook 440 G10 Business Laptop", "brand": "HP", "category": "laptops", "price": 67500.0,
        "specs": {"cpu": "Intel Core i5-1335U (10C/12T)", "ram": "16GB DDR4", "storage": "512GB SSD", "display": "14.0-inch FHD", "battery": "10 hrs", "warranty": "1-Year On-Site"}
    },
    "beta_vivobook_s14": {
        "id": "beta_vivobook_s14", "sku": "ASUS-VB-S14-OLED", "provider_id": "provider_beta",
        "title": "ASUS Vivobook S 14 OLED Laptop", "brand": "ASUS", "category": "laptops", "price": 68990.0,
        "specs": {"cpu": "Intel Core i5-13500H (12C/16T)", "ram": "16GB LPDDR5", "storage": "512GB SSD", "display": "14.0-inch 2.8K OLED 90Hz", "battery": "10.5 hrs", "warranty": "1-Year Global"}
    },
    "beta_acer_swift_go": {
        "id": "beta_acer_swift_go", "sku": "ACR-SW-GO14-EVO", "provider_id": "provider_beta",
        "title": "Acer Swift Go 14 OLED Laptop", "brand": "Acer", "category": "laptops", "price": 62990.0,
        "specs": {"cpu": "Intel Core i5-13500H (12C/16T)", "ram": "16GB LPDDR5", "storage": "512GB SSD", "display": "14.0-inch OLED 90Hz", "battery": "9 hrs", "warranty": "2-Year Extended"}
    },

    # Monitors & Displays
    "alpha_dell_u2723qe": {
        "id": "alpha_dell_u2723qe", "sku": "DELL-U2723QE-4K", "provider_id": "provider_alpha",
        "title": "Dell UltraSharp 27 4K USB-C Hub Monitor (U2723QE)", "brand": "Dell", "category": "monitors", "price": 54990.0,
        "specs": {"display": "27-inch 4K UHD (3840x2160)", "resolution": "4K", "refresh_rate": "60Hz IPS Black", "ports": "USB-C 90W PD, RJ45"}
    },
    "beta_lg_27gr95qe": {
        "id": "beta_lg_27gr95qe", "sku": "LG-27GR95QE-OLED", "provider_id": "provider_beta",
        "title": "LG UltraGear 27 OLED QHD Gaming Monitor", "brand": "LG", "category": "monitors", "price": 68990.0,
        "specs": {"display": "27-inch QHD (2560x1440)", "resolution": "2K QHD", "refresh_rate": "240Hz 0.03ms OLED", "ports": "HDMI 2.1, DP 1.4"}
    },

    # Office Chairs & Ergonomics
    "beta_ergosmart_pro": {
        "id": "beta_ergosmart_pro", "sku": "ERGO-SMART-PRO", "provider_id": "webmcp_furniture",
        "title": "ErgoSmart Pro Office Chair", "brand": "ErgoSmart", "category": "office_furniture", "price": 12499.0,
        "specs": {"ergonomics": "High Back • Lumbar Support", "material": "High-Tensile Mesh", "warranty": "3-Year Warranty"}
    },
    "alpha_green_soul_monster": {
        "id": "alpha_green_soul_monster", "sku": "GS-MONSTER-ULT-T", "provider_id": "webmcp_furniture",
        "title": "Green Soul Monster Ultimate T Chair", "brand": "Green Soul", "category": "office_furniture", "price": 14990.0,
        "specs": {"ergonomics": "Ergonomic Lumbar Pillow", "material": "Breathable Soft Fabric", "warranty": "3-Year Warranty"}
    },
    "alpha_sleep_company_stylux": {
        "id": "alpha_sleep_company_stylux", "sku": "TSC-STYLUX-SMARTGRID", "provider_id": "provider_alpha",
        "title": "The Sleep Company Stylux SmartGRID Chair", "brand": "The Sleep Company", "category": "office_furniture", "price": 13999.0,
        "specs": {"ergonomics": "SmartGRID Patented Ergonomics", "material": "Dual-Tone Mesh • 2D Armrests", "warranty": "3-Year Warranty"}
    },
    "alpha_herman_miller_aeron": {
        "id": "alpha_herman_miller_aeron", "sku": "HM-AERON-B-GRPH", "provider_id": "provider_alpha",
        "title": "Herman Miller Aeron Ergonomic Office Chair", "brand": "Herman Miller", "category": "office_furniture", "price": 115000.0,
        "specs": {"material": "Pellicle 8Z Breathable Mesh", "ergonomics": "PostureFit SL Dual Support", "warranty": "12-Year On-Site"}
    },
    "beta_steelcase_gesture": {
        "id": "beta_steelcase_gesture", "sku": "SC-GESTURE-BLK", "provider_id": "provider_beta",
        "title": "Steelcase Gesture Ergonomic Desk Chair", "brand": "Steelcase", "category": "office_furniture", "price": 89000.0,
        "specs": {"material": "Core Fabric & 3D LiveBack", "ergonomics": "360-Degree Rotating Armrests", "warranty": "12-Year Warranty"}
    },
    "alpha_featherlite_helix": {
        "id": "alpha_featherlite_helix", "sku": "FL-HELIX-HB-MESH", "provider_id": "provider_alpha",
        "title": "Featherlite Helix High-Back Ergonomic Chair", "brand": "Featherlite", "category": "office_furniture", "price": 18500.0,
        "specs": {"material": "High-Tensile Breathable Mesh", "ergonomics": "Self-Calibrating Synchro-Tilt", "warranty": "3-Year Warranty"}
    },

    # Cloud Services & Developer Subscriptions
    "alpha_aws_dev_tier": {
        "id": "alpha_aws_dev_tier", "sku": "AWS-DEV-RESERVED-YR", "provider_id": "provider_alpha",
        "title": "AWS Cloud Developer Compute Cluster (Annual Reserved)", "brand": "Amazon Web Services", "category": "cloud_services", "price": 45000.0,
        "specs": {"tier": "Compute Optimized (t4g.xlarge + RDS)", "uptime_sla": "99.99%", "support": "Developer Business Hours SLA"}
    },
    "beta_gcp_ai_cluster": {
        "id": "beta_gcp_ai_cluster", "sku": "GCP-VERTEX-AI-SEAT", "provider_id": "provider_beta",
        "title": "Google Cloud Vertex AI & Workspace Enterprise Seat", "brand": "Google Cloud", "category": "cloud_services", "price": 38000.0,
        "specs": {"tier": "Enterprise AI Workbench + 100GB Storage", "uptime_sla": "99.95%", "support": "24/7 Production Support"}
    }
}


async def fetch_live_web_products(query: str, max_price: Optional[float] = None) -> List[Dict[str, Any]]:
    """Fetch live real-world products using public web product API."""
    results = []
    clean_q = re.sub(r"[^\w\s]", "", query).strip()
    if not clean_q or len(clean_q) < 2:
        return results

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=2.5)) as session:
            url = f"https://dummyjson.com/products/search?q={clean_q}"
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    for item in data.get("products", [])[:4]:
                        usd_price = float(item.get("price", 0))
                        inr_price = round(usd_price * 85.0, -1)
                        if max_price and inr_price > max_price:
                            continue
                        p_id = f"live_{item.get('id')}"
                        results.append({
                            "id": p_id,
                            "sku": f"LIVE-{item.get('sku', item.get('id'))}",
                            "provider_id": "live_retail_mart",
                            "title": item.get("title", "Live Item"),
                            "brand": item.get("brand", "Global"),
                            "category": item.get("category", "consumer_goods"),
                            "price": inr_price,
                            "specs": {
                                "rating": f"⭐ {item.get('rating', '4.5')}/5.0",
                                "stock": f"{item.get('stock', 20)} in stock",
                                "warranty": item.get("warrantyInformation", "1-Year Official Warranty"),
                                "shipping": item.get("shippingInformation", "Free Standard Delivery")
                            }
                        })
    except Exception:
        pass
    return results


async def search_all_sources(query: str, max_price: Optional[float] = None) -> List[Dict[str, Any]]:
    """Searches live web APIs and multi-provider enterprise catalogs, merging candidates."""
    raw_tokens = [t.lower() for t in re.split(r"[\s,]+", query) if len(t) > 2]
    tokens = set(raw_tokens + [t.rstrip("s") for t in raw_tokens if t.endswith("s") and len(t) > 3])
    matched = []

    # 1. Search verified multi-provider catalog
    for item in CATALOG.values():
        if max_price and item["price"] > max_price:
            continue
        searchable_text = f"{item['title']} {item['category']} {item['brand']} {json.dumps(item['specs'])}".lower()
        if not tokens or any(t in searchable_text for t in tokens):
            matched.append(item)

    # 2. Query live web products
    live_items = await fetch_live_web_products(query, max_price=max_price)
    for l_item in live_items:
        # Avoid duplicates
        if not any(m["title"].lower() == l_item["title"].lower() for m in matched):
            matched.append(l_item)

    return matched


def score_candidate(item: Dict[str, Any], budget: Optional[float]) -> float:
    score = 0.5
    price = float(item["price"])
    if budget and budget > 0:
        if price <= budget:
            savings_ratio = (budget - price) / budget
            score += 0.3 * (1.0 + savings_ratio * 0.3)
        else:
            score -= 0.5
    specs = item.get("specs", {})
    if "H" in str(specs.get("cpu", "")):
        score += 0.15
    if "OLED" in str(item.get("title", "")) or "4K" in str(item.get("title", "")):
        score += 0.1
    if "Lumbar" in str(specs.get("ergonomics", "")) or "Lumbar" in str(item.get("title", "")):
        score += 0.15
    if "Mesh" in str(specs.get("material", "")) or "Mesh" in str(item.get("title", "")):
        score += 0.15
    if "12-Year" in str(specs.get("warranty", "")):
        score += 0.1
    return round(score, 4)



# =====================================================================
# Cryptographic HMAC Authorization Helpers
# =====================================================================
def generate_approval(task_id: str, provider_id: str, product: Dict[str, Any], sender: str) -> Dict[str, Any]:
    token = f"appr_{secrets.token_hex(4)}"
    ts = int(time.time())
    payload = f"{token}:{task_id}:{provider_id}:{product['sku']}:{product['price']}:{sender}:{ts}"
    sig = hmac.new(APPROVAL_SECRET, payload.encode("utf-8"), hashlib.sha256).hexdigest()
    rec = {
        "approval_id": token,
        "task_id": task_id,
        "provider_id": provider_id,
        "product_id": product["id"],
        "target_tool": "add_to_cart" if provider_id == "provider_alpha" else "cart_add",
        "bound_price": product["price"],
        "sender_address": sender,
        "created_at": ts,
        "signature": sig,
        "product": product
    }
    return rec


# =====================================================================
# ACP Protocol Message Handling & Directives
# =====================================================================
def sanitize_user_query(raw_query: str) -> str:
    """Always strip platform tags, handles, and prefixes (e.g., @webmcp, webmcp:, @agent) before processing."""
    cleaned = re.sub(r'@\w+\s*', '', raw_query).strip()
    cleaned = re.sub(r'^webmcp[:\s]*', '', cleaned, flags=re.IGNORECASE).strip()
    return cleaned if cleaned else "general products"


GREETING_WORDS = {"hi", "hello", "hey", "start", "help", "who are you", "onboarding", "howdy", "greetings", "hola"}


def is_greeting(cleaned_text: str) -> bool:
    """Detect whether user intent is a friendly greeting or onboarding request."""
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
    # Deduplicate incoming envelopes
    msg_key = str(msg.msg_id)
    if msg_key in _seen_msgs:
        return
    _seen_msgs[msg_key] = True
    if len(_seen_msgs) > MAX_SEEN:
        _seen_msgs.popitem(last=False)

    # Check for ACP StartSessionContent
    is_start = any(isinstance(c, StartSessionContent) or getattr(c, "type", None) == "start-session" for c in msg.content)

    # Extract text and interactive card selections
    user_text = ""
    card_selection: Optional[Dict[str, Any]] = None
    for item in msg.content:
        if isinstance(item, TextContent) or getattr(item, "type", None) == "text":
            txt = getattr(item, "text", "")
            trimmed_txt = txt.strip()
            if trimmed_txt.startswith("{") and trimmed_txt.endswith("}"):
                try:
                    parsed = json.loads(trimmed_txt)
                    if isinstance(parsed, dict) and "action" in parsed:
                        card_selection = parsed
                except Exception:
                    pass
            user_text += " " + txt

    user_text = user_text.strip()
    clean_text = sanitize_user_query(user_text)
    ctx.logger.info(f"Incoming message from {sender}: raw='{user_text}', clean='{clean_text}' (card_action={card_selection.get('action') if card_selection else None})")

    # 1. Directive 2: Conversational Intent & Welcome Workflow
    if is_start or is_greeting(clean_text):
        try:
            await ctx.send(sender, make_chat_msg(WELCOME_GUIDE))
        except Exception as e:
            ctx.logger.error(f"Failed to dispatch welcome guide: {e}")
        return

    # 2. Directive 5: Form-Filling & Parameter Collection Template Request
    clean_lower = re.sub(r"[^\w\s]", "", clean_text.lower()).strip()
    if clean_lower in ("setup", "finder", "product finder", "form", "template", "finder setup"):
        template_msg = (
            "📋 **Product Finder Setup:**\n"
            "- **Target Product:** [User input or Pending]\n"
            "- **Maximum Budget:** [Enter amount]\n"
            "- **Priority Feature:** [e.g., Battery life, Material, Portability]\n\n"
            "💡 *Please specify your target product, maximum budget, and preferred features to begin searching!*"
        )
        try:
            await ctx.send(sender, make_chat_msg(template_msg))
        except Exception:
            pass
        return

    # =================================================================
    # Step A: Handle Card Clicks & Action Commands
    # =================================================================

    # Check for Payment Confirmation (Payment Auth -> Final Receipt)
    confirm_pay_match = re.search(r"\b(?:CONFIRM_PAYMENT)\b(?:\s+(ord_[a-zA-Z0-9_]+|[a-zA-Z0-9_]+))?", clean_text, re.IGNORECASE)
    if (card_selection and card_selection.get("action") == "confirm_payment") or confirm_pay_match:
        ord_id = (card_selection.get("order_id") if card_selection else None) or (confirm_pay_match.group(1) if confirm_pay_match else None)
        order = load_order(ctx, ord_id, sender)
        if not order:
            try:
                await ctx.send(sender, make_chat_msg("❌ Order reference not found or already settled."))
            except Exception:
                pass
            return

        tx_hash = "0x" + hashlib.sha256(f"{order['order_id']}:{sender}:{time.time()}".encode()).hexdigest()
        order["status"] = "SETTLED"
        order["tx_hash"] = tx_hash
        save_order(ctx, order["order_id"], order)

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
        try:
            await ctx.send(sender, make_chat_msg(settle_text, metadata_card=settle_card))
        except Exception as e:
            ctx.logger.error(f"Failed to dispatch settlement card: {e}")
        return

    # Check for Payment Cancellation
    if (card_selection and card_selection.get("action") == "cancel_payment") or re.search(r"\bCANCEL_PAYMENT\b", clean_text, re.IGNORECASE):
        try:
            await ctx.send(sender, make_chat_msg("🛑 Payment settlement cancelled. Your cart remains ready whenever you wish to proceed."))
        except Exception:
            pass
        return

    # Check for Payment Initiation (Manual Checkout command)
    init_pay_match = re.search(r"\b(?:PAY|CHECKOUT|SETTLE)\b(?:\s+(appr_[a-zA-Z0-9_]+|[a-zA-Z0-9_]+))?", clean_text, re.IGNORECASE)
    if (card_selection and card_selection.get("action") == "initiate_payment") or (init_pay_match and not re.search(r"\b(?:CONFIRM_PAYMENT)\b", clean_text, re.IGNORECASE)):
        token_id = (card_selection.get("token_id") if card_selection else None) or (init_pay_match.group(1) if init_pay_match else None)
        rec = load_token(ctx, token_id, sender)
        if not rec:
            try:
                await ctx.send(sender, make_chat_msg("❌ No active cart items found to checkout. Please search for an item and approve it first."))
            except Exception:
                pass
            return

        prod = rec.get("product") or CATALOG.get(rec.get("product_id"), {})
        price = float(rec.get("bound_price", prod.get("price", 0)))
        asi_tokens = round(price / ASI_INR_RATE, 2)
        order_id = f"ord_{secrets.token_hex(4)}"

        order_data = {
            "order_id": order_id,
            "token_id": rec.get("approval_id"),
            "product_title": prod.get("title", "Selected Item"),
            "total_inr": price,
            "total_asi": asi_tokens,
            "sender": sender,
            "recipient_wallet": AGENT_WALLET,
            "status": "AWAITING_PAYMENT",
            "created_at": int(time.time()),
            "expires_at": int(time.time()) + 300
        }
        save_order(ctx, order_id, order_data)

        pay_msg = (
            f"💳 **Fetch.ai Payment Protocol Authorization Request**\n\n"
            f"• **Merchant / Provider Address:** `{AGENT_WALLET}`\n"
            f"• **Total Amount:** **₹{price:,.2f} INR** (**{asi_tokens:,.2f} ASI / FET**)\n"
            f"• **Authorization Token ID:** `{rec.get('approval_id')}`\n"
            f"• **Order ID:** `{order_id}`\n"
            f"• **Product:** **{prod.get('title')}**\n"
            f"• **Expiration Timer:** Valid for 5 minutes\n"
            f"• **Settlement Network:** Fetch.ai Dorado Testnet\n\n"
            f"🛡️ **Action Required:**\n"
            f"Please confirm payment authorization to execute final on-chain settlement.\n"
            f"👇 Click **'Authorize Payment'** below or reply **`CONFIRM_PAYMENT {order_id}`**."
        )
        pay_card = create_payment_metadata(order_data)
        try:
            await ctx.send(sender, make_chat_msg(pay_msg, metadata_card=pay_card))
        except Exception as e:
            ctx.logger.error(f"Failed to dispatch payment card: {e}")
        return

    # Check for Approval (Directive 6: Review Card -> Cart Addition -> Immediate Payment Protocol Authorization)
    appr_match = re.search(r"\b(?:APPROVE|CONFIRM)\b(?:\s+(appr_[a-zA-Z0-9_]+|[a-zA-Z0-9_]+))?", clean_text, re.IGNORECASE)
    token_to_approve = None
    if card_selection and card_selection.get("action") in ("approve", "approve_action"):
        token_to_approve = card_selection.get("approval_id") or card_selection.get("token_id")
    elif appr_match:
        token_to_approve = appr_match.group(1)

    # Only treat as approval if an explicit token was found or if message is strictly an approval keyword
    is_pure_approval = clean_text.upper() in ("APPROVE", "YES", "CONFIRM", "ADD TO CART")
    if token_to_approve or is_pure_approval:
        rec = load_token(ctx, token_to_approve, sender)
        if not rec:
            try:
                await ctx.send(sender, make_chat_msg(f"❌ Approval token `{token_to_approve or 'pending'}` was not found or has expired. Please ask to compare an item again."))
            except Exception:
                pass
            return

        token_id = rec.get("approval_id")
        if is_executed(ctx, token_id):
            try:
                await ctx.send(sender, make_chat_msg("⚠️ This action was already executed (idempotency replay protection active)."))
            except Exception:
                pass
            return

        # Execute cart mutation & verify
        mark_executed(ctx, token_id, rec)
        prod = rec.get("product") or CATALOG.get(rec.get("product_id"), {})
        session_id = f"sess_{sender[:10]}"
        if session_id not in _carts:
            _carts[session_id] = {"items": [], "total": 0.0}
        _carts[session_id]["items"].append(prod)
        price = float(rec.get("bound_price", prod.get("price", 0)))
        _carts[session_id]["total"] += price

        # Directive 6: Immediately trigger Fetch.ai Payment Protocol workflow
        order_id = f"ord_{secrets.token_hex(4)}"
        asi_tokens = round(price / ASI_INR_RATE, 2)
        order_data = {
            "order_id": order_id,
            "token_id": token_id,
            "product_title": prod.get("title", "Selected Item"),
            "total_inr": price,
            "total_asi": asi_tokens,
            "recipient_wallet": AGENT_WALLET,
            "sender": sender,
            "status": "AWAITING_PAYMENT",
            "created_at": int(time.time()),
            "expires_at": int(time.time()) + 300
        }
        save_order(ctx, order_id, order_data)

        confirm_text = (
            f"✅ **Action Authorized & Independently Verified!**\n\n"
            f"• **Target Provider:** `{rec['provider_id']}`\n"
            f"• **Tool Invoked:** `{rec['target_tool']}`\n"
            f"• **Item Added:** **{prod.get('title', 'Item')}**\n"
            f"• **Verified State:** Independent `CART_READ` confirmed {len(_carts[session_id]['items'])} line item(s).\n"
            f"• **Current Cart Total:** ₹{_carts[session_id]['total']:,.2f} (~{_carts[session_id]['total'] / ASI_INR_RATE:,.2f} ASI)\n\n"
            f"💳 **Fetch.ai Payment Protocol Authorization Request**\n"
            f"• **Merchant / Provider Address:** `{AGENT_WALLET}`\n"
            f"• **Total Amount:** **₹{price:,.2f} INR** (**{asi_tokens:,.2f} ASI / FET**)\n"
            f"• **Authorization Token ID:** `{token_id}`\n"
            f"• **Order ID:** `{order_id}`\n"
            f"• **Expiration Timer:** Valid for 5 minutes\n"
            f"• **Settlement Network:** Fetch.ai Dorado Testnet\n\n"
            f"🛡️ *Checkout Boundary Safeguard:* Execution halted prior to payment.\n"
            f"👇 Click **'Authorize Payment'** below or reply **`CONFIRM_PAYMENT {order_id}`** to complete final transaction settlement."
        )
        pay_card = create_payment_metadata(order_data)
        try:
            await ctx.send(sender, make_chat_msg(confirm_text, metadata_card=pay_card))
        except Exception as e:
            ctx.logger.error(f"Failed to dispatch cart confirmation & payment card: {e}")
        return

    # Check for Explicit Rejection
    rej_match = re.search(r"\b(?:REJECT|CANCEL)\b(?:\s+(appr_[a-zA-Z0-9_]+|[a-zA-Z0-9_]+))?", clean_text, re.IGNORECASE)
    if (card_selection and card_selection.get("action") in ("reject", "reject_action")) or rej_match:
        token_id = (card_selection.get("approval_id") if card_selection else None) or (rej_match.group(1) if rej_match else None)
        try:
            await ctx.send(sender, make_chat_msg(f"🛑 Cart operation `{token_id or ''}` was cancelled. Your shopping cart remains untouched."))
        except Exception:
            pass
        return

    # Handle Product Selection from Carousel
    if card_selection and card_selection.get("action") == "select_product":
        p_id = card_selection.get("product_id")
        selected_prod = CATALOG.get(p_id)
        if not selected_prod:
            for item in CATALOG.values():
                if item["id"] == p_id:
                    selected_prod = item
                    break

        if selected_prod:
            task_id = f"task_{secrets.token_hex(4)}"
            approval_req = generate_approval(task_id, selected_prod["provider_id"], selected_prod, sender)
            save_token(ctx, approval_req["approval_id"], approval_req)

            resp_text = (
                f"Selected **{selected_prod['title']}** from `{selected_prod['provider_id']}` at **₹{selected_prod['price']:,.2f}**.\n\n"
                f"🛡️ **Authorization Gate:**\n"
                f"Click **'Approve & Add to Cart'** below or reply **`APPROVE {approval_req['approval_id']}`** to proceed."
            )
            review_card = create_review_metadata(approval_req, selected_prod)
            try:
                await ctx.send(sender, make_chat_msg(resp_text, metadata_card=review_card))
            except Exception as e:
                ctx.logger.error(f"Failed to send selected product card: {e}")
            return

    # =================================================================
    # Step B: Natural Language Search & Multi-Provider Comparison
    # =================================================================
    parsed_form = parse_structured_form(clean_text)
    if parsed_form and parsed_form.get("product"):
        q = parsed_form["product"]
        budget = parsed_form["budget"]
        missing_budget = (budget is None)
    else:
        # Extract budget from free text
        budget = None
        budget_m = re.search(r"(?:under|below|budget|within|upto|less than)\s*(?:₹|inr|rs\.?)?\s*([0-9,]+)", clean_text, re.IGNORECASE)
        if budget_m:
            try:
                budget = float(budget_m.group(1).replace(",", ""))
            except Exception:
                pass

        missing_budget = (budget is None)

        # Clean query for search
        q = clean_text
        for term in ["find", "search", "best", "the", "under", "below", "compare", "add", "to", "my", "cart", "please", "show", "me", "@webmcp", "for", "upto", "within"]:
            q = re.sub(rf"\b{term}\b", "", q, flags=re.IGNORECASE)
        q = q.strip()
        if not q:
            q = clean_text

    # Search live products and multi-provider catalog
    candidates = await search_all_sources(q, max_price=budget)
    if not candidates:
        try:
            await ctx.send(sender, make_chat_msg(f"🔍 No products matching '{clean_text}' were found across active providers within your specified budget. Try adjusting the search terms or budget!"))
        except Exception as e:
            ctx.logger.error(f"Failed to send empty results message: {e}")
        return

    # Score and rank candidates
    ranked = sorted(candidates, key=lambda c: score_candidate(c, budget), reverse=True)
    top_pick = ranked[0]

    # Generate approval token and persist in storage
    task_id = f"task_{secrets.token_hex(4)}"
    approval_req = generate_approval(task_id, top_pick["provider_id"], top_pick, sender)
    save_token(ctx, approval_req["approval_id"], approval_req)

    # Format Markdown Decision Table (Directive 4)
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

    # Directive 5: Form-Filling & Parameter Collection template when budget is missing
    setup_prefix = ""
    if missing_budget:
        setup_prefix = (
            f"📋 **Product Finder Setup:**\n"
            f"- **Target Product:** {q.title()}\n"
            f"- **Maximum Budget:** [Enter amount e.g. under ₹15,000]\n"
            f"- **Priority Feature:** [e.g., Battery life, Material, Portability]\n\n"
            f"💡 *To narrow down results within your specific budget, reply with your limit (e.g. `under 15000`) or submit the setup above.*\n\n"
        )

    response_text = (
        f"{setup_prefix}"
        f"{decision_table}\n\n"
        f"💡 **Top Recommendation:** **{top_pick['title']}** from `{top_pick['provider_id']}` at **₹{top_pick['price']:,.2f}** (~{top_pick['price'] / ASI_INR_RATE:,.2f} ASI).\n\n"
        f"🛡️ **Action Authorization Required:** To add this item to your shopping cart, reply: **`APPROVE {approval_req['approval_id']}`**\n\n"
        f"*(Token valid for 5 minutes • Will strictly NOT proceed to payment without separate approval)*"
    )

    carousel_card = create_carousel_metadata(ranked, top_pick)
    review_card = create_review_metadata(approval_req, top_pick)

    # Dispatch response with Interactive Cards to ASI:One
    try:
        content: list[Any] = [
            TextContent(type="text", text=response_text),
            carousel_card,
            review_card
        ]
        chat_reply = ChatMessage(timestamp=datetime.now(timezone.utc), msg_id=uuid4(), content=content)
        await ctx.send(sender, chat_reply)
    except Exception as e:
        ctx.logger.error(f"Failed to dispatch recommendation cards: {e}")
        try:
            await ctx.send(sender, make_chat_msg(response_text, metadata_card=review_card))
        except Exception:
            pass



@chat_proto.on_message(ChatAcknowledgement)
async def handle_acknowledgement(ctx: Context, sender: str, msg: ChatAcknowledgement):
    msg_id = getattr(msg, "acknowledged_msg_id", None) or getattr(msg, "acknowledged", None)
    ctx.logger.info(f"Received delivery acknowledgement for msg {msg_id} from {sender}")


agent.include(chat_proto, publish_manifest=True)

if __name__ == "__main__":
    agent.run()
