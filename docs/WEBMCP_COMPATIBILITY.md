# WebMCP & MCP Compatibility Guide

## 1. Overview and Core Distinction

The **Dynamic WebMCP Agent Network** integrates two distinct paradigms of tool discovery and invocation:
1. **Browser WebMCP (Web Model Context Protocol)**: Front-end browser-native tool registration (`navigator.modelContext` / `window.modelContext`).
2. **Remote MCP (Model Context Protocol)**: Server-to-server or agent-to-server tool exposure over stdio, SSE, or WebSocket transports.

| Attribute | Browser WebMCP | Remote MCP |
| :--- | :--- | :--- |
| **Execution Context** | Client-side web page / browser tab | External process / remote server |
| **Discovery Mechanism** | `navigator.modelContext.getTools()` or declarative HTML tags | MCP initialization handshake (`tools/list`) |
| **State Scope** | User session, active cookies, DOM state, client-side memory | Backend database, API tokens, remote services |
| **Access Boundary** | Scoped to active web origin / page security boundary | Network-accessible via authenticated RPC |
| **Bridge Required** | **Yes** — Backend uAgent cannot directly invoke page scripts | **No** — Direct network RPC connection |

---

## 2. Browser WebMCP Specification

WebMCP (under active incubation in the W3C Web Machine Learning Community Group) provides a standardized API for websites to expose structured actions to AI agents without scraping:

### Imperative Tool Registration API
```javascript
if (navigator.modelContext) {
  navigator.modelContext.registerTool({
    name: "search_products",
    description: "Search products in store catalog by query and max budget.",
    inputSchema: {
      type: "object",
      properties: {
        query: { type: "string" },
        max_price: { type: "number" }
      },
      required: ["query"]
    },
    execute: async (args) => {
      const results = await storeApi.search(args.query, args.max_price);
      return JSON.stringify(results);
    }
  });
}
```

### Discovery Lifecycle
1. User navigates to a WebMCP-enabled website.
2. Web page registers available tools dynamically based on authentication and active route.
3. The WebMCP Browser Bridge discovers tools and broadcasts them to the **Dynamic Tool Registry**.
4. The **Dynamic Tool Router** maps the site-specific tool to a canonical capability (`PRODUCT_SEARCH`).
5. When invoked, the bridge securely tunnels execution into the page context and returns structured JSON output.

---

## 3. Remote MCP Specification

Remote MCP tools follow the standard JSON-RPC 2.0 lifecycle:
1. **Initialize Request**: Negotiates protocol version and client capabilities.
2. **`tools/list`**: Returns tool names, descriptions, and JSON Schema definitions.
3. **`tools/call`**: Executes the tool with validated arguments and returns structured `content` blocks.

---

## 4. Heterogeneous Provider Heterogeneity (The Problem Solved)

In real-world deployment, different websites expose overlapping capabilities with completely divergent tool names and argument schemas:

- **Provider Alpha (TechMart Online)**:
  - Tool: `search_products(query: string, max_price?: number)`
  - Tool: `get_product_details(product_id: string)`
  - Tool: `add_to_cart(session_id: string, product_id: string, quantity: number)`
- **Provider Beta (ElectroStore Pro)**:
  - Tool: `find_items(keywords: string, budget?: number)`
  - Tool: `fetch_specs(item_sku: string)`
  - Tool: `cart_add(session_id: string, item_sku: string, count: number)`
- **Provider Gamma (GlobalGadgets)**:
  - Tool: `catalog_search(filter_dict: object)`
  - Tool: `compare_specs(sku_list: array)`
  - Tool: `update_basket(basket_id: string, action: string, item_id: string)`

### The Solution: Canonical Capability Mapping
The Dynamic WebMCP Agent Network introduces a two-way schema translation layer:
1. Translates canonical user request (`PRODUCT_SEARCH`, budget: 70000, query: "laptop") into each provider's exact parameter schema.
2. Normalizes divergent output records into unified canonical models (`ProductRecord`).

---

## 5. Execution Modes & Fallback Hierarchy

To ensure 100% testability, safety, and reproducibility across environments:
1. `webmcp_browser`: Live browser context invocation via authenticated WebSocket/HTTP bridge.
2. `remote_mcp`: Direct stdio/SSE remote MCP server invocation.
3. `demo_adapter`: In-process deterministic provider adapter implementing identical schema validation, stateful cart storage, and realistic catalog data.

If a browser tab disconnects or a remote MCP server times out:
- Stale tools are marked `UNAVAILABLE`.
- The router automatically activates **Fallback Recovery**, re-routing to an alternative compatible provider without crashing the user session.
