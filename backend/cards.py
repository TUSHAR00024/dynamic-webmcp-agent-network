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
        cpu = specs.get("cpu", "Standard CPU")
        ram = specs.get("ram", "Standard RAM")
        battery = specs.get("battery", "Standard Battery")
        secondary_text = f"{cpu} • {ram} • {battery}"

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
