"""Agent-Driven Interactive Card Builders for Agentverse & ASI:One."""
import json
from typing import Any, Dict, List, Optional
from uagents_core.contrib.protocols.chat import MetadataContent


def build_product_carousel_card(
    candidates: List[Dict[str, Any]],
    top_recommendation: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Build an Agentverse carousel card payload showcasing ranked products."""
    top_id = top_recommendation.get("product_id") if top_recommendation else None
    items = []

    for item in candidates[:5]:  # Keep within 64 KB and UI limits
        p_id = item.get("product_id", "")
        name = item.get("name", "Product")
        price = item.get("price", 0)
        provider = item.get("provider_id", "Unknown")
        specs = item.get("specs", {})
        cpu = specs.get("cpu", "Standard CPU")
        ram = specs.get("ram", "Standard RAM")

        is_top = (p_id == top_id)
        badge = "⭐ Top Recommendation" if is_top else f"Provider: {provider}"

        items.append({
            "id": p_id,
            "title": f"{'⭐ ' if is_top else ''}{name}",
            "subtitle": f"₹{price:,.0f} • {provider}",
            "badge": badge,
            "description": f"{cpu} | {ram}",
            "action": {
                "type": "submit",
                "label": "Select Option",
                "payload": {
                    "action": "select_product",
                    "product_id": p_id,
                    "provider_id": provider
                }
            }
        })

    return {
        "card_kind": "carousel",
        "title": "Discovered Product Options",
        "items": items
    }


def build_approval_review_card(
    approval_req: Dict[str, Any],
    top_recommendation: Dict[str, Any]
) -> Dict[str, Any]:
    """Build an Agentverse review / approval card before state-changing cart mutation."""
    approval_id = approval_req.get("approval_id", "")
    bound_price = approval_req.get("bound_price", 0)
    provider_id = approval_req.get("provider_id", "")
    target_tool = approval_req.get("target_tool", "")

    return {
        "card_kind": "review",
        "title": "Action Authorization Required",
        "description": "Please review and confirm this irreversible or state-changing action before execution.",
        "item": {
            "title": top_recommendation.get("name", "Selected Item"),
            "price": f"₹{bound_price:,.2f}",
            "provider": provider_id,
            "tool": target_tool,
            "approval_token": approval_id
        },
        "actions": [
            {
                "type": "submit",
                "label": f"Approve ({approval_id})",
                "style": "primary",
                "payload": {
                    "action": "approve",
                    "approval_id": approval_id,
                    "text": f"APPROVE {approval_id}"
                }
            },
            {
                "type": "submit",
                "label": "Reject Action",
                "style": "danger",
                "payload": {
                    "action": "reject",
                    "approval_id": approval_id,
                    "text": f"REJECT {approval_id}"
                }
            }
        ]
    }


def create_card_metadata(card_payload: Dict[str, Any]) -> MetadataContent:
    """Serialize card payload into an ACP MetadataContent block conforming to Agentverse specifications."""
    serialized = json.dumps(card_payload)
    if len(serialized.encode("utf-8")) > 60 * 1024:
        # Safeguard within 64 KB limit
        card_payload["items"] = card_payload.get("items", [])[:3]
        serialized = json.dumps(card_payload)

    return MetadataContent(
        metadata={
            "mime_type": "application/vnd.agentverse.card+json",
            "card_payload": serialized
        }
    )
