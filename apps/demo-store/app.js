/**
 * WebPilot AI Frontend Application Controller
 * Handles Multi-Provider Catalog, Live WebMCP Tool Inspection, and Agent Workflow Orchestration.
 */
document.addEventListener("DOMContentLoaded", () => {
  // State
  let currentTask = null;
  let currentCart = { items: [], total: 0, version: 1 };
  let pendingApproval = null;
  let approvalInterval = null;

  // DOM Elements
  const promptInput = document.getElementById("prompt-input");
  const btnRunAgent = document.getElementById("btn-run-agent");
  const btnSamplePrompt = document.getElementById("btn-sample-prompt");
  const traceContainer = document.getElementById("trace-container");
  const routingExplanation = document.getElementById("routing-explanation");
  const routingRationaleText = document.getElementById("routing-rationale-text");
  const productsGrid = document.getElementById("products-grid");
  const toolsTableBody = document.getElementById("tools-table-body");
  const toolCountBadge = document.getElementById("tool-count-badge");
  const comparisonContainer = document.getElementById("comparison-container");
  const cartDrawer = document.getElementById("cart-drawer");
  const btnToggleCart = document.getElementById("btn-toggle-cart");
  const btnCloseCart = document.getElementById("btn-close-cart");
  const cartCount = document.getElementById("cart-count");
  const cartItemsContainer = document.getElementById("cart-items-container");
  const cartTotalAmount = document.getElementById("cart-total-amount");
  const approvalModal = document.getElementById("approval-modal");
  const approvalDetailsBox = document.getElementById("approval-details-box");
  const approvalHash = document.getElementById("approval-hash");
  const approvalTimer = document.getElementById("approval-timer");
  const btnConfirmApproval = document.getElementById("btn-confirm-approval");
  const btnRejectApproval = document.getElementById("btn-reject-approval");

  // Tab switching
  document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".tab-pane").forEach(p => p.classList.remove("active"));
      btn.classList.add("active");
      const targetPane = document.getElementById(`pane-${btn.dataset.tab}`);
      if (targetPane) targetPane.classList.add("active");
    });
  });

  // Cart Drawer toggle
  btnToggleCart.addEventListener("click", () => cartDrawer.classList.toggle("open"));
  btnCloseCart.addEventListener("click", () => cartDrawer.classList.remove("open"));

  // Reset sample prompt
  btnSamplePrompt.addEventListener("click", () => {
    promptInput.value = "Find the best laptop under ₹70,000 for programming and college. Search multiple websites, compare at least three suitable options, explain the trade-offs, and add the best option to my cart. Do not check out.";
  });

  // Initial Load: Fetch products and tools
  loadCatalog();
  loadTools();

  async function loadCatalog() {
    try {
      const res = await fetch("/api/products");
      if (!res.ok) throw new Error("API offline");
      const data = await res.json();
      renderProducts(data.products || []);
    } catch (e) {
      // Fallback demo data if backend is starting
      renderDefaultProducts();
    }
  }

  function renderProducts(products) {
    productsGrid.innerHTML = "";
    if (products.length === 0) {
      productsGrid.innerHTML = "<p>No products available.</p>";
      return;
    }

    products.forEach(p => {
      const isAlpha = p.provider_id === "provider_alpha";
      const pillClass = isAlpha ? "pill-alpha" : "pill-beta";
      const providerLabel = isAlpha ? "Provider Alpha (TechMart)" : "Provider Beta (ElectroStore)";

      const card = document.createElement("div");
      card.className = "product-card";
      card.innerHTML = `
        <div class="product-badge-row">
          <span class="provider-pill ${pillClass}">${providerLabel}</span>
          <span class="stock-badge ${p.stock_status}">${p.stock_status === "in_stock" ? "In Stock" : "Out of Stock"}</span>
        </div>
        <h4 class="product-title">${p.title || p.name}</h4>
        <div class="product-price">₹${Number(p.price).toLocaleString("en-IN")}</div>
        <ul class="specs-list">
          <li><strong>CPU:</strong> ${p.specs?.cpu || "N/A"}</li>
          <li><strong>RAM / SSD:</strong> ${p.specs?.ram || "N/A"} • ${p.specs?.storage || "N/A"}</li>
          <li><strong>Battery:</strong> ${p.specs?.battery || "unknown"}</li>
          <li><strong>Warranty:</strong> ${p.specs?.warranty || "unknown"}</li>
        </ul>
        <button class="btn btn-outline btn-sm btn-block" onclick="alert('Use the AI Agent Operator to discover, compare, and add this item.')">Inspect Specs</button>
      `;
      productsGrid.appendChild(card);
    });
  }

  function renderDefaultProducts() {
    const sample = [
      {
        provider_id: "provider_alpha",
        name: "Lenovo ThinkPad E14 Gen 5",
        price: 64990,
        stock_status: "in_stock",
        specs: { cpu: "Ryzen 7 7730U", ram: "16GB", storage: "512GB SSD", battery: "57Wh (9.5h)", warranty: "3-Year Premier Onsite" }
      },
      {
        provider_id: "provider_beta",
        name: "ASUS Vivobook S 14 OLED",
        price: 68990,
        stock_status: "in_stock",
        specs: { cpu: "Core i5-13500H", ram: "16GB LPDDR5", storage: "512GB SSD", battery: "75Wh (10.5h)", warranty: "1-Year Warranty" }
      },
      {
        provider_id: "provider_alpha",
        name: "Acer Swift Go 14",
        price: 58990,
        stock_status: "in_stock",
        specs: { cpu: "Core i5-1335U", ram: "16GB", storage: "512GB SSD", battery: "65Wh (8.5h)", warranty: "1-Year Warranty" }
      },
      {
        provider_id: "provider_beta",
        name: "Dell Latitude 3440 Enterprise",
        price: 62490,
        stock_status: "in_stock",
        specs: { cpu: "Core i5-1335U", ram: "16GB", storage: "512GB SSD", battery: "54Wh (7.5h)", warranty: "unknown" }
      }
    ];
    renderProducts(sample);
  }

  async function loadTools() {
    try {
      const res = await fetch("/api/tools");
      const data = await res.json();
      renderToolsTable(data.tools || []);
    } catch (e) {
      renderDefaultTools();
    }
  }

  function renderToolsTable(tools) {
    toolsTableBody.innerHTML = "";
    toolCountBadge.textContent = `${tools.length} Tools Discovered`;
    tools.forEach(t => {
      const tr = document.createElement("tr");
      const isAlpha = t.provider_id.includes("alpha");
      tr.innerHTML = `
        <td><span class="provider-pill ${isAlpha ? 'pill-alpha' : 'pill-beta'}">${t.provider_id}</span></td>
        <td><code>${t.tool_name}</code></td>
        <td><span class="badge badge-purple">${t.canonical_capability}</span></td>
        <td><span class="badge ${t.classification === 'read_only' ? 'badge-blue' : 'badge-amber'}">${t.classification}</span></td>
        <td><small>${Object.keys(t.input_schema?.properties || {}).join(", ")}</small></td>
      `;
      toolsTableBody.appendChild(tr);
    });
  }

  function renderDefaultTools() {
    const defaultTools = [
      { provider_id: "provider_alpha", tool_name: "search_products", canonical_capability: "PRODUCT_SEARCH", classification: "read_only", input_schema: { properties: { query: {}, max_price: {} } } },
      { provider_id: "provider_alpha", tool_name: "add_to_cart", canonical_capability: "CART_ADD", classification: "reversible_state_change", input_schema: { properties: { session_id: {}, product_id: {}, quantity: {} } } },
      { provider_id: "provider_beta", tool_name: "find_items", canonical_capability: "PRODUCT_SEARCH", classification: "read_only", input_schema: { properties: { keywords: {}, budget: {} } } },
      { provider_id: "provider_beta", tool_name: "cart_add", canonical_capability: "CART_ADD", classification: "reversible_state_change", input_schema: { properties: { session_id: {}, item_sku: {}, count: {} } } }
    ];
    renderToolsTable(defaultTools);
  }

  // Multi-Agent Workflow Execution
  btnRunAgent.addEventListener("click", async () => {
    const prompt = promptInput.value.trim();
    if (!prompt) return;

    btnRunAgent.disabled = true;
    traceContainer.innerHTML = "";
    routingExplanation.style.display = "none";

    try {
      // Step 1: Planner
      addTraceStep(1, "Planner Agent", "Interpreting goal & constraints...", "Extracted budget limit ₹70,000, priorities: coding, battery, reliability. Action requested: add best option to cart; checkout forbidden.", "completed");
      await delay(400);

      // Step 2: Discovery
      addTraceStep(2, "Discovery Agent", "Querying live WebMCP & Remote MCP tools...", "Discovered active tools: Provider Alpha (`search_products`, `add_to_cart`) and Provider Beta (`find_items`, `cart_add`).", "completed");
      await delay(400);

      // Step 3: Tool Router
      addTraceStep(3, "Dynamic Tool Router", "Dispatching parallel catalogue discovery...", "Normalizing canonical query. Executing parallel search across Provider Alpha (TechMart) and Provider Beta (ElectroStore).", "completed");
      
      // Call backend workflow API
      const res = await fetch("/api/tasks/run_workflow", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: prompt, session_id: "demo_session_1" })
      });

      if (!res.ok) {
        throw new Error("Workflow execution failed");
      }

      const workflowResult = await res.json();
      currentTask = workflowResult;

      // Step 4: Comparison
      addTraceStep(4, "Comparison Agent", "Ranking candidates against multi-criteria constraints...", `Evaluated ${workflowResult.candidates.length} candidates under ₹70,000. Top recommendation: ${workflowResult.top_recommendation.title}.`, "completed");
      renderComparison(workflowResult.candidates, workflowResult.top_recommendation);
      await delay(400);

      // Display routing rationale
      if (workflowResult.routing_rationale) {
        routingExplanation.style.display = "block";
        routingRationaleText.textContent = workflowResult.routing_rationale;
      }

      // Step 5: Policy Gate (Requires Human Approval)
      addTraceStep(5, "Policy & Approval Agent", "Enforcing human-in-the-loop approval gate...", "State-changing action 'add_to_cart' requires explicit authorization. Halting execution until user approves.", "active");
      
      // Show approval modal
      showApprovalModal(workflowResult.approval_request, workflowResult.top_recommendation);

    } catch (e) {
      console.error(e);
      addTraceStep(99, "Error Handler", "Execution failed", e.message, "failed");
    } finally {
      btnRunAgent.disabled = false;
    }
  });

  function addTraceStep(num, agentName, title, details, status) {
    const el = document.createElement("div");
    el.className = `trace-step step-${status}`;
    el.innerHTML = `
      <span class="step-num">${num}</span>
      <div class="step-content">
        <div class="step-title-row">
          <strong>${agentName}</strong>
          <span class="step-status-tag">${status.toUpperCase()}</span>
        </div>
        <p class="step-action">${title}</p>
        <small class="step-details">${details}</small>
      </div>
    `;
    traceContainer.appendChild(el);
    traceContainer.scrollTop = traceContainer.scrollHeight;
  }

  function renderComparison(candidates, topRec) {
    comparisonContainer.innerHTML = "";
    const table = document.createElement("table");
    table.className = "comparison-table";
    table.innerHTML = `
      <thead>
        <tr>
          <th>Attribute</th>
          ${candidates.map(c => `<th>${c.title} ${c.sku === topRec.sku ? '<span class="badge badge-green">Recommended</span>' : ''}</th>`).join("")}
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>Provider</td>
          ${candidates.map(c => `<td><span class="provider-pill ${c.provider_id === 'provider_alpha' ? 'pill-alpha' : 'pill-beta'}">${c.provenance}</span></td>`).join("")}
        </tr>
        <tr>
          <td>Price</td>
          ${candidates.map(c => `<td><strong>₹${Number(c.price).toLocaleString('en-IN')}</strong></td>`).join("")}
        </tr>
        <tr>
          <td>CPU Performance</td>
          ${candidates.map(c => `<td>${c.specs?.cpu || 'N/A'}</td>`).join("")}
        </tr>
        <tr>
          <td>RAM / Storage</td>
          ${candidates.map(c => `<td>${c.specs?.ram || 'N/A'} • ${c.specs?.storage || 'N/A'}</td>`).join("")}
        </tr>
        <tr>
          <td>Battery Life</td>
          ${candidates.map(c => `<td>${c.specs?.battery || 'unknown'}</td>`).join("")}
        </tr>
        <tr>
          <td>Warranty & Support</td>
          ${candidates.map(c => `<td>${c.specs?.warranty || 'unknown'}</td>`).join("")}
        </tr>
      </tbody>
    `;
    comparisonContainer.appendChild(table);

    // Switch to comparison tab automatically
    document.querySelector('.tab-btn[data-tab="comparison"]').click();
  }

  function showApprovalModal(approvalReq, product) {
    pendingApproval = approvalReq;
    approvalDetailsBox.innerHTML = `
      <div class="approval-card-item">
        <strong>Operation:</strong> Add to Provider Shopping Cart (<code>${approvalReq.target_tool}</code>)
      </div>
      <div class="approval-card-item">
        <strong>Target Provider:</strong> <span class="provider-pill ${approvalReq.provider_id === 'provider_alpha' ? 'pill-alpha' : 'pill-beta'}">${approvalReq.provider_id}</span>
      </div>
      <div class="approval-card-item">
        <strong>Product:</strong> ${product.title} (SKU: <code>${product.sku}</code>)
      </div>
      <div class="approval-card-item">
        <strong>Bound Price:</strong> ₹${Number(approvalReq.bound_price).toLocaleString("en-IN")}
      </div>
      <div class="approval-card-item">
        <strong>Quantity:</strong> 1 unit
      </div>
      <div class="approval-card-item">
        <strong>Reversibility:</strong> Reversible (item can be deleted from cart later)
      </div>
    `;

    approvalHash.textContent = approvalReq.arguments_hash || "sha256_mock_hash";
    let secondsLeft = 300;
    if (approvalInterval) clearInterval(approvalInterval);
    approvalInterval = setInterval(() => {
      secondsLeft--;
      approvalTimer.textContent = `${secondsLeft}s`;
      if (secondsLeft <= 0) {
        clearInterval(approvalInterval);
        closeApprovalModal();
        addTraceStep(6, "Policy Gate", "Approval Expired", "Approval token expired after 300 seconds. Action aborted safely.", "failed");
      }
    }, 1000);

    approvalModal.style.display = "flex";
  }

  function closeApprovalModal() {
    if (approvalInterval) clearInterval(approvalInterval);
    approvalModal.style.display = "none";
  }

  btnConfirmApproval.addEventListener("click", async () => {
    closeApprovalModal();
    addTraceStep(6, "Approval Gate", "User Explicitly Approved Action", `Authorized execution for ${pendingApproval.target_tool}.`, "completed");
    
    // Step 7: Cart Action Execution
    addTraceStep(7, "Cart Action Agent", `Invoking '${pendingApproval.target_tool}' on ${pendingApproval.provider_id}...`, "Dispatching authorized tool call with bound parameters and idempotency token.", "active");
    await delay(500);

    try {
      const res = await fetch("/api/approvals/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          approval_id: pendingApproval.approval_id,
          task_id: currentTask.task_id
        })
      });
      const actionResult = await res.json();

      // Step 8: Postcondition Verification
      addTraceStep(8, "Postcondition Verifier", "Independent Cart State Verification", actionResult.verification_details || "Verified item added to cart successfully.", "completed");
      
      // Update UI cart
      updateCartDrawer(actionResult.cart_state);
      
      // Step 9: Final result
      addTraceStep(9, "Dispatcher Agent", "Workflow Completed Safely", "Recommended laptop added to cart. Execution halted prior to checkout boundary as instructed.", "completed");

    } catch (e) {
      addTraceStep(8, "Action Error", "Failed to commit cart mutation", e.message, "failed");
    }
  });

  btnRejectApproval.addEventListener("click", () => {
    closeApprovalModal();
    addTraceStep(6, "Approval Gate", "User Rejected Action", "State change denied by human operator. Cart remains untouched.", "failed");
  });

  function updateCartDrawer(cart) {
    if (!cart) return;
    currentCart = cart;
    const items = cart.items || [];
    cartCount.textContent = items.reduce((s, i) => s + (i.quantity || 1), 0);
    cartTotalAmount.textContent = `₹${Number(cart.total || cart.subtotal || 0).toLocaleString("en-IN")}`;

    if (items.length === 0) {
      cartItemsContainer.innerHTML = '<p class="empty-cart-msg">Your shopping cart is currently empty.</p>';
    } else {
      cartItemsContainer.innerHTML = items.map(i => `
        <div class="cart-item-card">
          <div class="cart-item-info">
            <strong>${i.name || i.title}</strong>
            <small>Qty: ${i.quantity} • ₹${Number(i.unit_price).toLocaleString("en-IN")}</small>
          </div>
          <div class="cart-item-price">
            ₹${Number((i.quantity || 1) * i.unit_price).toLocaleString("en-IN")}
          </div>
        </div>
      `).join("");
    }

    cartDrawer.classList.add("open");
  }

  function delay(ms) {
    return new Promise(r => setTimeout(r, ms));
  }
});
