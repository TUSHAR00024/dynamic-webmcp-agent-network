# Dynamic WebMCP Agent Network — 2-Minute Demonstration Script

**Tagline:** "From brittle screen clicks to structured, dynamic tool networks."

---

### 0:00 – 0:18: Problem Statement & Vision
*"Conventional web AI agents rely on brittle computer-use approaches: taking screenshots, guessing CSS selectors, and clicking coordinates. When website layouts change, these agents break.*

*We built the **Dynamic WebMCP Agent Network** for Fetch-A-Thon 3.0. Instead of clicking pixels, our multi-agent system dynamically discovers structured website tools through WebMCP and Remote MCP, normalizes their schemas at runtime, routes requests across disparate providers, and enforces human-in-the-loop authorization."*

---

### 0:18 – 0:45: Dynamic Discovery & Heterogeneous Providers
*(Screen shows Demo Store at `http://localhost:8000`)*

*"Look at our live store. We have two distinct providers:
- **Provider Alpha (TechMart)** exposes WebMCP tools directly in the browser page: `search_products(query, max_price)` and `add_to_cart(session_id, product_id, quantity)`.
- **Provider Beta (ElectroStore Pro)** exposes Remote MCP tools with completely different schemas: `find_items(keywords, budget)` and `cart_add(session_id, item_sku, count)`.

Our Planner and Discovery agents do not have hardcoded tool names. They map these into canonical capabilities: `PRODUCT_SEARCH` and `CART_ADD`."*

---

### 0:45 – 1:15: Parallel Routing & Grounded Comparison
*(Screen shows prompt entered and Execution Trace running)*

*"We enter our user's goal:
> 'Find the best laptop under ₹70,000 for programming and college. Search multiple websites, compare at least three options, explain trade-offs, and add the best option to my cart. Do not check out.'

Watch the **Dynamic Tool Router** in action:
1. It queries both providers simultaneously via parallel thread dispatch.
2. The Schema Normalizer transforms the canonical query into Alpha's and Beta's unique parameters.
3. The Comparison Agent ranks candidates against multi-criteria constraints (coding CPU, battery, reliability).
4. Lenovo ThinkPad E14 is selected with a composite score of 93/100, and ASUS Vivobook OLED is compared side-by-side with full spec provenance."*

---

### 1:15 – 1:40: Human Approval Gate & Postcondition Verification
*(Screen shows Approval Modal popping up with cryptographic hash)*

*"Because adding an item to a cart is a state-changing action, our **Policy Agent** intercepts execution. It issues a short-lived approval token cryptographically bound to the exact product, price (₹64,990), and provider.

We click **Authorize & Execute**.
The Action Agent invokes Alpha's `add_to_cart` tool.
Crucially, our system doesn't just trust an HTTP 200 code—it immediately executes an independent `CART_READ` postcondition query to verify that the cart state in the database actually holds the item.

And notice: **the checkout boundary is strictly enforced**. The system halts before order submission or payment, exactly as instructed."*

---

### 1:40 – 2:00: Automatic Failover & Conclusion
*(Screen shows Provider Gamma fallback test and Agentverse manifest)*

*"To guarantee reliability, when a provider fails—like Provider Gamma throwing a simulated 503 error—our router detects the failure and instantly re-routes to the next best provider without user interruption.

Integrated with Fetch.ai's Agent Chat Protocol (ACP) and discoverable via ASI:One, the Dynamic WebMCP Agent Network turns the web into an open, structured API for autonomous agents."*
