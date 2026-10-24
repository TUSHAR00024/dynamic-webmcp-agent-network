# ASI:One Agent-Driven Interactive Card Payloads

This document documents the verified JSON card payloads used by the **Dynamic WebMCP Agent Operator** via the Agent Chat Protocol (ACP). These payloads strictly conform to the [Agentverse Predefined Card Schemas](https://docs.agentverse.ai/documentation/advanced-usages/predefined-card-schemas.md).

> **Playground Validation:** You can paste these raw `card_payload` JSON objects directly into the [ASI:One Card Playground](https://asi1.ai/developer/card-playground) to visually inspect and test interactions.

---

## 1. Product Carousel Card (`card_kind: "carousel"`)

Presented in response to product discovery queries, displaying ranked options side-by-side with trade-off badges and action selections.

### Metadata Envelope (`MetadataContent.metadata`)
```json
{
  "card_protocol_version": "1",
  "requires_card_interaction": "true",
  "card_kind": "carousel",
  "card_payload": "{\"card_kind\": \"carousel\", \"items\": [...]}"
}
```

### Raw `card_payload` JSON
```json
{
  "card_kind": "carousel",
  "items": [
    {
      "id": "alpha_thinkpad_e14",
      "title": "Lenovo ThinkPad E14 Gen 5",
      "subtitle": "₹62,990 • provider_alpha",
      "badges": [
        "⭐ Top Pick"
      ],
      "secondary_text": "AMD Ryzen 7 7730U • 16GB DDR4 • 57Wh Battery",
      "primary_cta": {
        "label": "Select Option",
        "selection": {
          "action": "select_product",
          "product_id": "alpha_thinkpad_e14",
          "provider_id": "provider_alpha"
        }
      }
    },
    {
      "id": "beta_vivobook_15",
      "title": "ASUS Vivobook 15 OLED",
      "subtitle": "₹64,990 • provider_beta",
      "badges": [],
      "secondary_text": "Intel Core i5-13500H • 16GB LPDDR5 • 70Wh Battery",
      "primary_cta": {
        "label": "Select Option",
        "selection": {
          "action": "select_product",
          "product_id": "beta_vivobook_15",
          "provider_id": "provider_beta"
        }
      }
    },
    {
      "id": "alpha_hp_pavilion",
      "title": "HP Pavilion 14 Plus",
      "subtitle": "₹66,990 • provider_alpha",
      "badges": [],
      "secondary_text": "Intel Core i5-1340P • 16GB • 51Wh Battery",
      "primary_cta": {
        "label": "Select Option",
        "selection": {
          "action": "select_product",
          "product_id": "alpha_hp_pavilion",
          "provider_id": "provider_alpha"
        }
      }
    }
  ]
}
```

---

## 2. Authorization Review Card (`card_kind: "review"`)

Presented when the user requests a state-changing cart mutation, requiring explicit confirmation before invoking retailer tools.

### Metadata Envelope (`MetadataContent.metadata`)
```json
{
  "card_protocol_version": "1",
  "requires_card_interaction": "true",
  "card_kind": "review",
  "card_payload": "{\"card_kind\": \"review\", \"title\": \"Authorize Cart Operation\", ...}"
}
```

### Raw `card_payload` JSON
```json
{
  "card_kind": "review",
  "title": "Authorize Cart Operation",
  "rows": [
    {
      "label": "Product",
      "value": "Lenovo ThinkPad E14 Gen 5"
    },
    {
      "label": "Price",
      "value": "₹62,990.00"
    },
    {
      "label": "Provider",
      "value": "provider_alpha"
    },
    {
      "label": "Tool",
      "value": "add_to_cart"
    },
    {
      "label": "Approval Token",
      "value": "appr_7b8a4f91e2"
    },
    {
      "label": "Policy Boundary",
      "value": "Cart Addition Only (No Checkout)"
    }
  ],
  "approve_cta": {
    "label": "Approve & Add to Cart",
    "primary": true,
    "selection": {
      "action": "approve",
      "approval_id": "appr_7b8a4f91e2"
    }
  },
  "reject_cta": {
    "label": "Reject Action",
    "selection": {
      "action": "reject",
      "approval_id": "appr_7b8a4f91e2"
    }
  }
}
```

---

## 3. Client Interaction & Return Format

When a user taps an action button in ASI:One, the client emits a message back to the agent:
1. **Direct JSON CTA Selection (Primary)**:
   ```json
   {"action": "approve", "approval_id": "appr_7b8a4f91e2"}
   ```
2. **Natural Language Confirmation (Conversational)**:
   ```text
   APPROVE appr_7b8a4f91e2
   ```
The agent router in `backend/uagent_app.py` handles both formats seamlessly.
