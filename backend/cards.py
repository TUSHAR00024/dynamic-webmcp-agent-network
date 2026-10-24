"""Agent-Driven Interactive Card Builders for Agentverse & ASI:One."""
import json
from typing import Any, Dict, List, Optional
from uagents_core.contrib.protocols.chat import MetadataContent


def build_product_carousel_card(
    candidates: List[Dict[str, Any]],
    top_recommendation: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Build an Agentverse carousel card payload showcasing ranked products conforming to predefined schemas."""
    top_id = None
    if top_recommendation:
        top_id = top_recommendation.get("product_id") or top_recommendation.get("sku")

    items = []
    for item in candidates[:5]:  # Keep well within 64 KB and UI limits
        p_id = item.get("product_id") or item.get("sku", "")
        # ProductRecord uses 'title'; fall back to 'name' if present
        title = item.get("title") or item.get("name", "Product Option")
        price = float(item.get("price", 0))
        provider = item.get("provider_id", "Unknown")

        specs = item.get("specs", {})
        # Domain-adaptive secondary text
        if specs.get("refresh_rate") or specs.get("resolution"):
            disp = specs.get("display") or specs.get("screen", "Monitor")
            rr = specs.get("refresh_rate", "")
            res = specs.get("resolution", "")
            secondary_text = f"{disp} • {res} • {rr}".strip(" •")
        elif specs.get("ergonomics") or specs.get("material"):
            mat = specs.get("material", "Ergonomic Build")
            ergo = specs.get("ergonomics", "Adjustable")
            secondary_text = f"{mat} • {ergo}"
        elif specs.get("uptime_sla") or specs.get("tier"):
            tier = specs.get("tier", "Cloud Tier")
            sla = specs.get("uptime_sla", "99.99%")
            secondary_text = f"{tier} • SLA: {sla}"
        elif specs.get("cpu") and specs.get("cpu") != "unknown":
            cpu = specs.get("cpu", "Standard CPU")
            ram = specs.get("ram", "Standard RAM")
            battery = specs.get("battery", "Standard Battery")
            secondary_text = f"{cpu} • {ram} • {battery}"
        else:
            secondary_text = "Verified Specifications"

        is_top = bool(top_id and p_id == top_id)
        badges = ["⭐ Top Pick"] if is_top else []

        items.append({
            "id": p_id,
            "title": title,
            "subtitle": f"₹{price:,.0f} • {provider}",
            "badges": badges,
            "secondary_text": secondary_text,
            "primary_cta": {
                "label": "Select Option",
                "selection": {
                    "action": "select_product",
                    "product_id": p_id,
                    "provider_id": provider
                }
            }
        })

    return {
        "card_kind": "carousel",
        "items": items
    }


def build_approval_review_card(
    approval_req: Dict[str, Any],
    top_recommendation: Dict[str, Any]
) -> Dict[str, Any]:
    """Build an Agentverse review / approval card before state-changing cart mutation."""
    approval_id = approval_req.get("approval_id", "")
    bound_price = float(approval_req.get("bound_price", 0))
    provider_id = approval_req.get("provider_id", "")
    target_tool = approval_req.get("target_tool", "")

    # Ensure real product title is extracted from ProductRecord
    title = top_recommendation.get("title") or top_recommendation.get("name", "Selected Item")

    rows = [
        {"label": "Product", "value": title},
        {"label": "Price", "value": f"₹{bound_price:,.2f}"},
        {"label": "Provider", "value": provider_id},
        {"label": "Tool", "value": target_tool},
        {"label": "Approval Token", "value": approval_id},
        {"label": "Policy Boundary", "value": "Cart Addition Only (No Checkout)"}
    ]

    return {
        "card_kind": "review",
        "title": "Authorize Cart Operation",
        "rows": rows,
        "approve_cta": {
            "label": "Approve & Add to Cart",
            "primary": True,
            "selection": {
                "action": "approve",
                "approval_id": approval_id
            }
        },
        "reject_cta": {
            "label": "Reject Action",
            "selection": {
                "action": "reject",
                "approval_id": approval_id
            }
        }
    }


def create_card_metadata(card_payload: Dict[str, Any], card_kind: str) -> MetadataContent:
    """Serialize card payload into an ACP MetadataContent block conforming strictly to Agentverse specifications."""
    serialized = json.dumps(card_payload)
    if len(serialized.encode("utf-8")) > 60 * 1024 and "items" in card_payload:
        card_payload["items"] = card_payload["items"][:2]
        serialized = json.dumps(card_payload)

    # Agentverse interactive cards specification requires:
    # 1. card_protocol_version: "1"
    # 2. requires_card_interaction: "true"
    # 3. card_kind: "carousel"|"detail"|"form"|"review"|"custom"
    # 4. card_payload: <JSON string>
    return MetadataContent(
        type="metadata",
        metadata={
            "card_protocol_version": "1",
            "requires_card_interaction": "true",
            "card_kind": card_kind,
            "card_payload": serialized
        }
    )


def create_carousel_metadata(
    candidates: List[Dict[str, Any]],
    top_recommendation: Optional[Dict[str, Any]] = None
) -> MetadataContent:
    """Helper to generate ACP MetadataContent for carousel cards."""
    payload = build_product_carousel_card(candidates, top_recommendation)
    return create_card_metadata(payload, "carousel")


def create_review_metadata(
    approval_req: Dict[str, Any],
    top_recommendation: Dict[str, Any]
) -> MetadataContent:
    """Helper to generate ACP MetadataContent for review cards."""
    payload = build_approval_review_card(approval_req, top_recommendation)
    return create_card_metadata(payload, "review")


def build_payment_review_card(order: Dict[str, Any]) -> Dict[str, Any]:
    """Build an Agentverse review / approval card for Fetch.ai Ledger settlement."""
    return {
        "card_kind": "review",
        "title": "💳 Authorize Fetch.ai Settlement",
        "rows": [
            {"label": "Order Reference", "value": order.get("order_id", "")},
            {"label": "Product", "value": order.get("product_title", "Selected Item")},
            {"label": "Total Amount (INR)", "value": f"₹{float(order.get('total_inr', 0)):,.2f}"},
            {"label": "Settlement Amount (ASI)", "value": f"{float(order.get('total_asi', 0)):,.2f} ASI"},
            {"label": "Recipient Wallet", "value": order.get("recipient_wallet", "")},
            {"label": "Payment Protocol", "value": "Fetch.ai Agent Chat Protocol (ACP-Pay v1.0)"},
            {"label": "Ledger Network", "value": "Fetch.ai Dorado Testnet"}
        ],
        "approve_cta": {
            "label": "Authorize Payment (ASI Token)",
            "primary": True,
            "selection": {
                "action": "confirm_payment",
                "order_id": order.get("order_id", "")
            }
        },
        "reject_cta": {
            "label": "Cancel Payment",
            "selection": {
                "action": "cancel_payment",
                "order_id": order.get("order_id", "")
            }
        }
    }


def create_payment_metadata(order: Dict[str, Any]) -> MetadataContent:
    """Helper to generate ACP MetadataContent for payment authorization review cards."""
    payload = build_payment_review_card(order)
    return create_card_metadata(payload, "review")


def build_settlement_detail_card(order: Dict[str, Any], tx_hash: str) -> Dict[str, Any]:
    """Build settlement confirmation detail card."""
    return {
        "card_kind": "detail",
        "title": "🎉 Payment Settled & Order Confirmed!",
        "rows": [
            {"label": "Order ID", "value": order.get("order_id", "")},
            {"label": "Product", "value": order.get("product_title", "")},
            {"label": "Amount Settled", "value": f"{float(order.get('total_asi', 0)):,.2f} ASI (₹{float(order.get('total_inr', 0)):,.2f})"},
            {"label": "Transaction Hash", "value": f"{tx_hash[:18]}...{tx_hash[-10:]}" if len(tx_hash) > 28 else tx_hash},
            {"label": "Settlement Ledger", "value": "Fetch.ai Dorado Testnet"},
            {"label": "Merchant Wallet", "value": order.get("recipient_wallet", "")},
            {"label": "Fulfillment Status", "value": "DISPATCH_AUTHORIZED"}
        ]
    }


def create_settlement_metadata(order: Dict[str, Any], tx_hash: str) -> MetadataContent:
    """Helper to generate ACP MetadataContent for settlement confirmation detail cards."""
    payload = build_settlement_detail_card(order, tx_hash)
    return create_card_metadata(payload, "detail")

