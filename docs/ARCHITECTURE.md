# Dynamic WebMCP Agent Network — System Architecture

## 1. System Overview

**Dynamic WebMCP Agent Network** is a multi-agent orchestration and routing framework designed for **Fetch-A-Thon 3.0**. It dynamically discovers, normalizes, scores, and executes structured tools exposed by disparate websites (via WebMCP) and remote servers (via MCP).

```text
                               +-------------------------------------+
                               |           USER / CLIENT             |
                               +-------------------------------------+
                                                  |
                                                  v
                               +-------------------------------------+
                               |        ASI:One Conversation         |
                               +-------------------------------------+
                                                  |
                                                  v
                               +-------------------------------------+
                               |       ACP Dispatcher Agent          |
                               +-------------------------------------+
                                                  |
                                                  v
                               +-------------------------------------+
                               |            Planner Agent            |
                               +-------------------------------------+
                                                  |
                                                  v
                               +-------------------------------------+
                               |        Dynamic Tool Registry        |
                               |    (Canonical Capabilities Map)     |
                               +-------------------------------------+
                                                  |
                                                  v
                               +-------------------------------------+
                               |         Dynamic Tool Router         |
                               |    (Scoring, Filtering, Fallback)   |
                               +-------------------------------------+
                                       /                     \
                                      /                       \
                                     v                         v
                   +------------------------+      +------------------------+
                   |  Browser WebMCP Bridge |      |   Remote MCP Adapter   |
                   +------------------------+      +------------------------+
                               |                               |
                               v                               v
                   +------------------------+      +------------------------+
                   | Provider A (TechMart)  |      | Provider B (Electro)   |
                   | `search_products`      |      | `find_items`           |
                   | `add_to_cart`          |      | `cart_add`             |
                   +------------------------+      +------------------------+
                                       \                      /
                                        \                    /
                                         v                  v
                               +-------------------------------------+
                               |      Research & Comparison Agents   |
                               +-------------------------------------+
                                                  |
                                                  v
                               +-------------------------------------+
                               |      Policy & Approval Gate         |
                               +-------------------------------------+
                                                  |
                                                  v
                               +-------------------------------------+
                               |         Cart Action Agent           |
                               +-------------------------------------+
                                                  |
                                                  v
                               +-------------------------------------+
                               |       Postcondition Verifier        |
                               +-------------------------------------+
                                                  |
                                                  v
                               +-------------------------------------+
                               |             Audit Agent             |
                               +-------------------------------------+
```

---

## 2. Agent Responsibilities & Message Flow

| Agent | Identity | Primary Responsibility |
| :--- | :--- | :--- |
| **Dispatcher** | `dispatcher_agent` | Receives ACP/ASI:One messages, tracks sessions, delivers structured cards and text back to the human. |
| **Planner** | `planner_agent` | Deconstructs user requests into structured constraints and required capabilities (`PRODUCT_SEARCH`, `CART_ADD`). |
| **Discovery** | `discovery_agent` | Scans registered browser WebMCP sessions and remote MCP servers; harvests live schemas and metadata. |
| **Routing** | `routing_agent` | Ranks eligible providers using a multi-factor scoring function, handles parallel dispatch and automatic fallback. |
| **Research** | `research_agent` | Executes search and detail queries across selected providers; attributes provenance and flags unknown specs. |
| **Comparison**| `comparison_agent`| Ranks normalized products against constraints, computes transparent composite scores, and details trade-offs. |
| **Policy** | `policy_agent` | Classifies actions (read-only vs state-changing vs financial), enforces human-in-the-loop approval, binds tokens. |
| **Cart Action**| `cart_agent` | Invokes provider-specific cart tool using exact bound arguments; prevents double-execution via idempotency keys. |
| **Audit** | `audit_agent` | Records verifiable execution traces with start/finish timestamps, correlation IDs, and sanitizes secrets. |

---

## 3. Dynamic Tool Registry & Canonical Capabilities

Instead of hardcoding tool names, the system organizes tools under **Canonical Capabilities**:

```text
                        Canonical Capability
                          [PRODUCT_SEARCH]
                                 |
         +-----------------------+-----------------------+
         |                                               |
         v                                               v
Provider Alpha (TechMart)                       Provider Beta (ElectroStore)
Tool: `search_products`                         Tool: `find_items`
Input Schema:                                   Input Schema:
  - query: string (required)                      - keywords: string (required)
  - max_price: number (optional)                  - budget: number (optional)
Output:                                         Output:
  - products: Array<{id, name, price...}>         - items: Array<{item_sku, title, cost...}>
         |                                               |
         +-----------------------+-----------------------+
                                 |
                                 v
               Schema Normalizer (Two-Way Translation)
Canonical Request: { query: "laptop", max_price: 70000 }
  -> Alpha: { query: "laptop", max_price: 70000 }
  -> Beta:  { keywords: "laptop", budget: 70000 }
```

---

## 4. Provider Scoring & Ranking Algorithm

When a capability is requested, the router evaluates candidate providers using normalized weights:

$$\text{Score} = w_{\text{match}} \cdot S_{\text{match}} + w_{\text{quality}} \cdot S_{\text{quality}} + w_{\text{freshness}} \cdot S_{\text{fresh}} + w_{\text{reliability}} \cdot S_{\text{rel}} - w_{\text{latency}} \cdot S_{\text{lat}} - w_{\text{cost}} \cdot S_{\text{cost}}$$

Default normalized weights:
- Capability Match ($w_{\text{match}} = 0.35$)
- Data Quality & Completeness ($w_{\text{quality}} = 0.25$)
- Historical Reliability ($w_{\text{reliability}} = 0.20$)
- Freshness ($w_{\text{freshness}} = 0.10$)
- Latency Penalty ($w_{\text{latency}} = 0.10$)

Hard constraints (e.g., maximum budget, required cart capability) are filtered **before** scoring. A high reliability score never overrides an incompatible tool schema or missing parameter.

---

## 5. Security, Approval Tokens, and Verification

1. **Permission Classification**:
   - `READ_ONLY`: `PRODUCT_SEARCH`, `PRODUCT_DETAILS`, `CART_READ` -> Automated execution allowed.
   - `REVERSIBLE_STATE_CHANGE`: `CART_ADD`, `CART_REMOVE` -> Policy-driven human confirmation.
   - `CONSEQUENTIAL`: `CHECKOUT_PREVIEW`, `ORDER_SUBMIT`, `PAYMENT` -> Explicit approval token required; stopped by default.
2. **Cryptographic Token Binding**:
   - Approval tokens are computed using SHA-256 over `(task_id, provider_id, tool_name, arguments_hash, bound_price)`.
   - Any price drift or parameter tampering immediately invalidates the approval token.
   - Time-to-live: 300 seconds (5 minutes).
3. **Authoritative Postcondition Verification**:
   - The action agent does not trust HTTP status codes. After invoking `add_to_cart` or `cart_add`, it independently calls `CART_READ` on the provider to verify that the item SKU and quantity actually exist in state.
