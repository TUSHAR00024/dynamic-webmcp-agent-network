"""Canonical Capability Definitions and Rules for Dynamic WebMCP Agent Network."""
from typing import Any, Dict, List, Set
from backend.models.tool import ToolClassification


class CanonicalCapability:
    PRODUCT_SEARCH = "PRODUCT_SEARCH"
    PRODUCT_DETAILS = "PRODUCT_DETAILS"
    PRODUCT_COMPARISON = "PRODUCT_COMPARISON"
    CART_READ = "CART_READ"
    CART_ADD = "CART_ADD"
    CART_REMOVE = "CART_REMOVE"
    CHECKOUT_PREVIEW = "CHECKOUT_PREVIEW"
    ORDER_SUBMIT = "ORDER_SUBMIT"
    PAYMENT_INITIATE = "PAYMENT_INITIATE"


CAPABILITY_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    CanonicalCapability.PRODUCT_SEARCH: {
        "description": "Search catalogue for products matching query, budget, and filter constraints.",
        "classification": ToolClassification.READ_ONLY,
        "required_canonical_inputs": ["query"],
        "optional_canonical_inputs": ["max_price", "category", "brand", "limit"],
        "expected_canonical_outputs": ["products", "count"]
    },
    CanonicalCapability.PRODUCT_DETAILS: {
        "description": "Fetch comprehensive technical specifications and real-time inventory status for an item.",
        "classification": ToolClassification.READ_ONLY,
        "required_canonical_inputs": ["product_id"],
        "optional_canonical_inputs": [],
        "expected_canonical_outputs": ["product"]
    },
    CanonicalCapability.CART_READ: {
        "description": "Inspect active cart items, subtotal, and state version for a session.",
        "classification": ToolClassification.READ_ONLY,
        "required_canonical_inputs": ["session_id"],
        "optional_canonical_inputs": [],
        "expected_canonical_outputs": ["session_id", "items", "total", "cart_version"]
    },
    CanonicalCapability.CART_ADD: {
        "description": "Add an item to the provider shopping cart. Reversible state change.",
        "classification": ToolClassification.REVERSIBLE_STATE_CHANGE,
        "required_canonical_inputs": ["session_id", "product_id", "quantity"],
        "optional_canonical_inputs": [],
        "expected_canonical_outputs": ["session_id", "product_id", "quantity", "cart_version"]
    },
    CanonicalCapability.CART_REMOVE: {
        "description": "Remove an item from the provider shopping cart.",
        "classification": ToolClassification.REVERSIBLE_STATE_CHANGE,
        "required_canonical_inputs": ["session_id", "product_id"],
        "optional_canonical_inputs": [],
        "expected_canonical_outputs": ["session_id", "product_id", "cart_version"]
    },
    CanonicalCapability.CHECKOUT_PREVIEW: {
        "description": "Calculate order totals, applicable taxes, and verify cart integrity prior to checkout.",
        "classification": ToolClassification.CONSEQUENTIAL_ACTION,
        "required_canonical_inputs": ["session_id", "expected_total"],
        "optional_canonical_inputs": [],
        "expected_canonical_outputs": ["order_draft_id", "total", "currency"]
    },
    CanonicalCapability.ORDER_SUBMIT: {
        "description": "Submit a finalized order. Consequential financial action requiring explicit human confirmation.",
        "classification": ToolClassification.CONSEQUENTIAL_ACTION,
        "required_canonical_inputs": ["order_draft_id", "confirmation_token"],
        "optional_canonical_inputs": [],
        "expected_canonical_outputs": ["order_id", "status"]
    }
}
