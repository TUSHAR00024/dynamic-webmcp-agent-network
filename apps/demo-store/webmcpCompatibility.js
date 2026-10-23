/**
 * WebMCP Compatibility Layer & Tool Registration Polyfill
 * Conforms to the W3C Web Machine Learning Community Group WebMCP proposal.
 */
(function () {
  class ModelContextRegistry {
    constructor() {
      this.tools = new Map();
      this.origin = window.location.origin;
    }

    registerTool(declaration) {
      if (!declaration.name || typeof declaration.execute !== "function") {
        throw new Error("Invalid tool declaration: 'name' and executable 'execute' function are required.");
      }
      this.tools.set(declaration.name, declaration);
      console.log(`[WebMCP] Registered tool '${declaration.name}' into modelContext registry.`);
    }

    getTools() {
      return Array.from(this.tools.values()).map(t => ({
        name: t.name,
        description: t.description,
        inputSchema: t.inputSchema,
        canonical_capability: t.canonical_capability || "UNKNOWN",
        requires_approval: !!t.requires_approval
      }));
    }

    async execute(toolName, args) {
      const tool = this.tools.get(toolName);
      if (!tool) {
        throw new Error(`WebMCP Tool '${toolName}' not found in active modelContext.`);
      }
      console.log(`[WebMCP] Executing tool '${toolName}' with arguments:`, args);
      return await tool.execute(args);
    }
  }

  // Expose on navigator and window
  const context = new ModelContextRegistry();
  window.modelContext = context;
  if (!navigator.modelContext) {
    navigator.modelContext = context;
  }

  // Register Provider Alpha WebMCP Tools directly into the browser page context
  context.registerTool({
    name: "search_products",
    description: "Search TechMart catalog for laptops by keyword query and max budget.",
    canonical_capability: "PRODUCT_SEARCH",
    inputSchema: {
      type: "object",
      properties: {
        query: { type: "string" },
        max_price: { type: "number" }
      },
      required: ["query"]
    },
    execute: async (args) => {
      const res = await fetch("/api/providers/alpha/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(args)
      });
      return await res.json();
    }
  });

  context.registerTool({
    name: "get_product_details",
    description: "Fetch comprehensive hardware specs and inventory status for an item from TechMart.",
    canonical_capability: "PRODUCT_DETAILS",
    inputSchema: {
      type: "object",
      properties: {
        product_id: { type: "string" }
      },
      required: ["product_id"]
    },
    execute: async (args) => {
      const res = await fetch(`/api/providers/alpha/details?product_id=${encodeURIComponent(args.product_id)}`);
      return await res.json();
    }
  });

  context.registerTool({
    name: "add_to_cart",
    description: "Add a product to the TechMart user shopping cart (Reversible State Change).",
    canonical_capability: "CART_ADD",
    requires_approval: true,
    inputSchema: {
      type: "object",
      properties: {
        session_id: { type: "string" },
        product_id: { type: "string" },
        quantity: { type: "integer" }
      },
      required: ["session_id", "product_id", "quantity"]
    },
    execute: async (args) => {
      const res = await fetch("/api/providers/alpha/cart/add", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(args)
      });
      return await res.json();
    }
  });

  context.registerTool({
    name: "get_cart",
    description: "Inspect active shopping cart items and calculated subtotal on TechMart.",
    canonical_capability: "CART_READ",
    inputSchema: {
      type: "object",
      properties: {
        session_id: { type: "string" }
      },
      required: ["session_id"]
    },
    execute: async (args) => {
      const res = await fetch(`/api/providers/alpha/cart?session_id=${encodeURIComponent(args.session_id)}`);
      return await res.json();
    }
  });

  // Automatically sync with Backend WebMCP Bridge on load
  window.syncWithWebMCPBridge = async function () {
    try {
      const tools = context.getTools();
      const sessionId = localStorage.getItem("webmcp_session_id") || "browser_session_" + Math.random().toString(36).substring(2, 9);
      localStorage.setItem("webmcp_session_id", sessionId);

      const resp = await fetch("/api/bridge/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          origin_url: window.location.origin,
          tools: tools
        })
      });
      const data = await resp.json();
      console.log("[WebMCP Bridge] Successfully synced with backend router:", data);
      return data;
    } catch (e) {
      console.warn("[WebMCP Bridge] Local bridge sync offline or running in mock mode:", e);
    }
  };

  window.addEventListener("DOMContentLoaded", () => {
    window.syncWithWebMCPBridge();
  });
})();
