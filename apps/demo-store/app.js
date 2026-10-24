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
  let allProducts = [];
  let currentCategoryFilter = "all";

  // Pre-configured multi-domain sample prompts
  const samplePrompts = {
    laptops: "Find the best laptop under ₹70,000 for programming and college. Search multiple websites, compare at least three suitable options, explain the trade-offs, and add the best option to my cart. Do not check out.",
    furniture: "Find the best ergonomic office chair under ₹40,000 with lumbar support and 3D armrests. Search multiple websites, compare options, explain the trade-offs, and add the best option to my cart. Do not check out.",
    monitors: "Find high-resolution 4K or 165Hz monitors under ₹60,000 suitable for programming and design work. Compare options across websites and add the best option to my cart. Do not check out.",
    cloud_services: "Find enterprise cloud compute credits or software subscriptions under ₹35,000 for developer workloads. Compare options and add the best option to my cart. Do not check out."
  };

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

  // Domain Preset Chips
  const promptChips = document.querySelectorAll(".prompt-chip");
  promptChips.forEach(chip => {
    chip.addEventListener("click", () => {
      promptChips.forEach(c => c.classList.remove("active"));
      chip.classList.add("active");
      const domain = chip.dataset.domain;
      if (domain && samplePrompts[domain]) {
        promptInput.value = samplePrompts[domain];
        setCategoryFilter(domain);
      }
    });
  });

  // Category Filter Pills
  const categoryPills = document.querySelectorAll(".category-pill");
  categoryPills.forEach(pill => {
    pill.addEventListener("click", () => {
      setCategoryFilter(pill.dataset.category);
    });
  });

  function setCategoryFilter(category) {
    currentCategoryFilter = category || "all";
    categoryPills.forEach(p => {
      if (p.dataset.category === currentCategoryFilter) {
        p.classList.add("active");
      } else {
        p.classList.remove("active");
      }
    });
    renderFilteredProducts();
  }

  // Reset sample prompt
  btnSamplePrompt.addEventListener("click", () => {
    promptInput.value = samplePrompts.laptops;
    promptChips.forEach(c => c.classList.toggle("active", c.dataset.domain === "laptops"));
    setCategoryFilter("all");
  });

  // Initial Load: Fetch products and tools
  loadCatalog();
  loadTools();

  async function loadCatalog() {
    try {
      const res = await fetch("/api/products");
      if (!res.ok) throw new Error("API offline");
      const data = await res.json();
      allProducts = data.products || [];
      updateCategoryCounts();
      renderFilteredProducts();
    } catch (e) {
      // Fallback demo data across domains if backend is starting
      renderDefaultProducts();
    }
  }

  function hasValidSpec(val) {
    if (val === null || val === undefined) return false;
    const str = String(val).trim().toLowerCase();
    return str !== "" && str !== "unknown" && str !== "n/a" && str !== "undefined" && str !== "none" && str !== "null";
  }

  function detectCategory(p) {
    if (!p) return "general";

    // 1. Direct category check on product or nested specs
    const cat = (p.category || p.specs?.category || "").toString().toLowerCase().trim();
    if (cat) {
      if (cat.includes("chair") || cat.includes("furniture") || cat.includes("desk")) return "furniture";
      if (cat.includes("monitor") || cat.includes("display") || cat.includes("screen")) return "monitors";
      if (cat.includes("cloud") || cat.includes("software") || cat.includes("sub") || cat.includes("service")) return "cloud_services";
      if (cat.includes("laptop") || cat.includes("notebook")) return "laptops";
    }

    // 2. Title & name keyword check
    const title = (p.title || p.name || "").toString().toLowerCase();
    if (title.includes("chair") || title.includes("ergonomic") || title.includes("featherlite") || title.includes("steelcase")) return "furniture";
    if (title.includes("monitor") || title.includes("ultrasharp") || title.includes("odyssey") || title.includes("4k") || title.includes("165hz")) return "monitors";
    if (title.includes("cloud") || title.includes("aws") || title.includes("jetbrains") || title.includes("compute")) return "cloud_services";
    if (title.includes("laptop") || title.includes("thinkpad") || title.includes("vivobook") || title.includes("swift go") || title.includes("inspiron")) return "laptops";

    // 3. Concrete specs check (ignoring "unknown")
    const s = p.specs || {};
    if (hasValidSpec(s.material) || hasValidSpec(s.ergonomics) || hasValidSpec(s.weight_capacity)) return "furniture";
    if (hasValidSpec(s.refresh_rate) || hasValidSpec(s.resolution) || hasValidSpec(s.panel_type)) return "monitors";
    if (hasValidSpec(s.tier) || hasValidSpec(s.uptime_sla) || hasValidSpec(s.subscription) || hasValidSpec(s.ide_support)) return "cloud_services";
    if (hasValidSpec(s.cpu) || (hasValidSpec(s.ram) && hasValidSpec(s.storage))) return "laptops";

    return "general";
  }

  function getCategoryLabel(cat) {
    switch (cat) {
      case "laptops": return "💻 Laptop";
      case "monitors": return "🖥️ Monitor";
      case "furniture": return "🪑 Office Furniture";
      case "cloud_services": return "☁️ Cloud & Software";
      default: return "📦 General";
    }
  }

  function formatProductSpecs(p) {
    const s = p.specs || {};
    const cat = detectCategory(p);

    if (cat === "laptops") {
      return `
        <li><strong>CPU:</strong> ${s.cpu || "N/A"}</li>
        <li><strong>RAM / SSD:</strong> ${s.ram || "N/A"} • ${s.storage || "N/A"}</li>
        <li><strong>Display:</strong> ${s.display || "N/A"}</li>
        <li><strong>Battery:</strong> ${s.battery || "N/A"}</li>
        <li><strong>Warranty:</strong> ${s.warranty || "N/A"}</li>
      `;
    }

    if (cat === "monitors") {
      return `
        <li><strong>Display:</strong> ${s.screen_size || ""} ${s.resolution || "High-Res"}</li>
        <li><strong>Refresh Rate:</strong> ${s.refresh_rate || "60Hz"}</li>
        <li><strong>Panel & Color:</strong> ${s.panel_type || "IPS"} ${s.color_gamut ? "• " + s.color_gamut : ""}</li>
        <li><strong>Ports / Stand:</strong> ${s.ports || s.stand || "HDMI / DP"}</li>
        <li><strong>Warranty:</strong> ${s.warranty || "N/A"}</li>
      `;
    }

    if (cat === "furniture") {
      return `
        <li><strong>Material:</strong> ${s.material || s.frame || "Ergonomic Mesh"}</li>
        <li><strong>Ergonomics:</strong> ${s.ergonomics || "Adjustable Lumbar Support"}</li>
        <li><strong>Weight Capacity:</strong> ${s.weight_capacity || "120+ kg"}</li>
        <li><strong>Warranty:</strong> ${s.warranty || s.guarantee || "N/A"}</li>
      `;
    }

    if (cat === "cloud_services") {
      return `
        <li><strong>Tier / Plan:</strong> ${s.tier || s.subscription || "Enterprise Tier"}</li>
        <li><strong>Allocation:</strong> ${s.vcpus || ""} ${s.ram ? "• " + s.ram : (s.ide_support || "")}</li>
        <li><strong>Uptime SLA:</strong> ${s.uptime_sla || "99.9%"}</li>
        <li><strong>Support / License:</strong> ${s.support || s.warranty || "Dedicated Support"}</li>
      `;
    }

    // Dynamic fallback for any other open domain
    const keys = Object.keys(s).slice(0, 4);
    if (keys.length === 0) {
      return `<li><strong>Details:</strong> Standard specifications apply</li>`;
    }
    return keys.map(k => {
      const label = k.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase());
      return `<li><strong>${label}:</strong> ${s[k]}</li>`;
    }).join("");
  }

  function updateCategoryCounts() {
    const counts = { all: allProducts.length, laptops: 0, monitors: 0, furniture: 0, cloud_services: 0 };
    allProducts.forEach(p => {
      const cat = detectCategory(p);
      if (counts[cat] !== undefined) {
        counts[cat]++;
      }
    });

    const elAll = document.getElementById("count-all");
    const elLaptops = document.getElementById("count-laptops");
    const elMonitors = document.getElementById("count-monitors");
    const elFurniture = document.getElementById("count-furniture");
    const elCloud = document.getElementById("count-cloud");

    if (elAll) elAll.textContent = counts.all;
    if (elLaptops) elLaptops.textContent = counts.laptops;
    if (elMonitors) elMonitors.textContent = counts.monitors;
    if (elFurniture) elFurniture.textContent = counts.furniture;
    if (elCloud) elCloud.textContent = counts.cloud_services;
  }

  function renderFilteredProducts() {
    let filtered = allProducts;
    if (currentCategoryFilter !== "all") {
      filtered = allProducts.filter(p => detectCategory(p) === currentCategoryFilter);
    }
    renderProducts(filtered);
  }

  function renderProducts(products) {
    productsGrid.innerHTML = "";
    if (products.length === 0) {
      productsGrid.innerHTML = `
        <div style="grid-column: 1 / -1; padding: 2.5rem; text-align: center; color: var(--text-muted);">
          <p>No products found in this category.</p>
        </div>`;
      return;
    }

    products.forEach(p => {
      const isAlpha = p.provider_id === "provider_alpha";
      const pillClass = isAlpha ? "pill-alpha" : "pill-beta";
      const providerLabel = isAlpha ? "Provider Alpha (TechMart)" : "Provider Beta (ElectroStore)";
      const cat = detectCategory(p);
      const catLabel = getCategoryLabel(cat);

      const card = document.createElement("div");
      card.className = "product-card";
      card.innerHTML = `
        <div class="product-badge-row">
          <span class="provider-pill ${pillClass}">${providerLabel}</span>
          <span class="category-badge">${catLabel}</span>
        </div>
        <div class="product-badge-row" style="margin-top: -0.25rem; margin-bottom: 0.5rem;">
          <span class="stock-badge ${p.stock_status || 'in_stock'}">${(p.stock_status || "in_stock") === "in_stock" ? "● In Stock" : "○ Out of Stock"}</span>
        </div>
        <h4 class="product-title">${p.title || p.name}</h4>
        <div class="product-price">₹${Number(p.price).toLocaleString("en-IN")}</div>
        <ul class="specs-list">
          ${formatProductSpecs(p)}
        </ul>
        <button class="btn btn-outline btn-sm btn-block" onclick="alert('Use the AI Agent Operator to discover, compare, and add this item.')">Inspect Specs</button>
      `;
      productsGrid.appendChild(card);
    });
  }

  function renderDefaultProducts() {
    allProducts = [
      {
        provider_id: "provider_alpha",
        name: "Lenovo ThinkPad E14 Gen 5",
        category: "laptops",
        price: 64990,
        stock_status: "in_stock",
        specs: { cpu: "Ryzen 7 7730U", ram: "16GB", storage: "512GB SSD", battery: "57Wh (9.5h)", warranty: "3-Year Premier Onsite" }
      },
      {
        provider_id: "provider_beta",
        name: "ASUS Vivobook S 14 OLED",
        category: "laptops",
        price: 68990,
        stock_status: "in_stock",
        specs: { cpu: "Core i5-13500H", ram: "16GB LPDDR5", storage: "512GB SSD", battery: "75Wh (10.5h)", warranty: "1-Year Warranty" }
      },
      {
        provider_id: "provider_alpha",
        name: "Dell UltraSharp 27 4K USB-C Hub Monitor (U2723QE)",
        category: "monitors",
        price: 54990,
        stock_status: "in_stock",
        specs: { screen_size: "27-inch", resolution: "4K UHD (3840 x 2160)", refresh_rate: "60Hz", panel_type: "IPS Black", color_gamut: "100% sRGB, 98% DCI-P3", stand: "Height/Pivot/Tilt", warranty: "3-Year Advanced Exchange" }
      },
      {
        provider_id: "provider_beta",
        name: "Samsung Odyssey G5 27 QHD 165Hz Curved Gaming Monitor",
        category: "monitors",
        price: 21990,
        stock_status: "in_stock",
        specs: { screen_size: "27-inch Curved 1000R", resolution: "QHD (2560 x 1440)", refresh_rate: "165Hz (1ms MPRT)", panel_type: "VA Panel", color_gamut: "HDR10", ports: "HDMI 2.0, DisplayPort 1.2", warranty: "3-Year Warranty" }
      },
      {
        provider_id: "provider_beta",
        name: "Steelcase Series 1 Ergonomic Office Task Chair",
        category: "furniture",
        price: 38990,
        stock_status: "in_stock",
        specs: { material: "LiveBack 3D Micro Knit & High-Density Foam", ergonomics: "Height-adjustable lumbar, 4D adjustable armrests, weight-activated synchro tilt", weight_capacity: "181 kg (400 lbs)", warranty: "12-Year Multi-Shift Warranty" }
      },
      {
        provider_id: "provider_alpha",
        name: "Featherlite Helix High-Back Ergonomic Office Chair",
        category: "furniture",
        price: 18990,
        stock_status: "in_stock",
        specs: { material: "Breathable Korean Mesh & Aluminum Alloy", ergonomics: "Adjustable Lumbar Support, 3D Armrests, Multi-lock Synchro Tilt", weight_capacity: "135 kg", warranty: "3-Year Manufacturer Warranty" }
      },
      {
        provider_id: "provider_alpha",
        name: "AWS Cloud Compute Enterprise Tier Credits",
        category: "cloud_services",
        price: 34990,
        stock_status: "in_stock",
        specs: { tier: "Enterprise Cloud Compute Tier", vcpus: "32 vCPUs Allocated", ram: "128GB Cloud Memory Pool", uptime_sla: "99.99%", support: "24/7 Enterprise Dedicated Support", warranty: "Enterprise Cloud SLA" }
      },
      {
        provider_id: "provider_beta",
        name: "JetBrains All Products Pack Annual Developer Subscription",
        category: "cloud_services",
        price: 24990,
        stock_status: "in_stock",
        specs: { subscription: "Annual All Products Commercial License", ide_support: "IntelliJ IDEA, PyCharm, WebStorm, CLion, GoLand, Rider", uptime_sla: "100% Floating Cloud Licensing", support: "Standard Business Support", warranty: "Continuous Software Updates" }
      }
    ];
    updateCategoryCounts();
    renderFilteredProducts();
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
      const displayPrompt = prompt.length > 70 ? prompt.slice(0, 67) + "..." : prompt;
      addTraceStep(1, "Planner Agent", "Interpreting goal & constraints...", `Parsing request: "${displayPrompt}". Normalizing budget, domain attributes, and safety boundary (no checkout).`, "completed");
      await delay(400);

      // Step 2: Discovery
      addTraceStep(2, "Discovery Agent", "Querying live WebMCP & Remote MCP tools...", "Discovered active tools: Provider Alpha (`search_products`, `add_to_cart`) and Provider Beta (`find_items`, `cart_add`).", "completed");
      await delay(400);

      // Step 3: Tool Router
      addTraceStep(3, "Dynamic Tool Router", "Dispatching parallel catalogue discovery...", "Normalizing canonical query across domains. Executing parallel search across Provider Alpha (TechMart) and Provider Beta (ElectroStore).", "completed");
      
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
      const budgetNote = workflowResult.budget ? `under ₹${Number(workflowResult.budget).toLocaleString("en-IN")}` : "meeting all constraints";
      addTraceStep(4, "Comparison Agent", "Ranking candidates against multi-criteria constraints...", `Evaluated ${workflowResult.candidates.length} candidates ${budgetNote}. Top recommendation: ${workflowResult.top_recommendation.title}.`, "completed");
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
    if (!candidates || candidates.length === 0) {
      comparisonContainer.innerHTML = "<p class='empty-state'>No candidate products to compare.</p>";
      return;
    }

    // Determine domain of dominant candidate
    const dominantCat = detectCategory(topRec || candidates[0]);
    let specRows = [];

    if (dominantCat === "furniture") {
      specRows = [
        { label: "Ergonomics & Adjustability", get: c => c.specs?.ergonomics || c.specs?.frame },
        { label: "Material & Build", get: c => c.specs?.material || c.specs?.frame },
        { label: "Weight Capacity", get: c => c.specs?.weight_capacity },
        { label: "Warranty & Support", get: c => c.specs?.warranty || c.specs?.guarantee }
      ];
    } else if (dominantCat === "monitors") {
      specRows = [
        { label: "Display & Resolution", get: c => [c.specs?.screen_size, c.specs?.resolution].filter(hasValidSpec).join(" ") },
        { label: "Refresh Rate", get: c => c.specs?.refresh_rate },
        { label: "Panel & Color Gamut", get: c => [c.specs?.panel_type, c.specs?.color_gamut].filter(hasValidSpec).join(" • ") },
        { label: "Ports / Stand Ergonomics", get: c => [c.specs?.ports, c.specs?.stand].filter(hasValidSpec).join(" • ") },
        { label: "Warranty & Support", get: c => c.specs?.warranty }
      ];
    } else if (dominantCat === "cloud_services") {
      specRows = [
        { label: "Tier / Edition", get: c => c.specs?.tier || c.specs?.subscription },
        { label: "Allocated Resources", get: c => [c.specs?.vcpus, c.specs?.ram, c.specs?.ide_support].filter(hasValidSpec).join(" • ") },
        { label: "Uptime SLA", get: c => c.specs?.uptime_sla },
        { label: "Support Level", get: c => c.specs?.support || c.specs?.warranty }
      ];
    } else if (dominantCat === "laptops") {
      specRows = [
        { label: "CPU Performance", get: c => c.specs?.cpu },
        { label: "RAM / Storage", get: c => [c.specs?.ram, c.specs?.storage].filter(hasValidSpec).join(" • ") },
        { label: "Battery Life", get: c => c.specs?.battery },
        { label: "Display", get: c => c.specs?.display },
        { label: "Warranty & Support", get: c => c.specs?.warranty }
      ];
    } else {
      // Dynamic union of candidate specs keys
      const allCandidateKeys = new Set();
      candidates.forEach(c => {
        Object.keys(c.specs || {}).forEach(k => {
          if (hasValidSpec(c.specs[k]) && k !== "category" && k !== "attributes") {
            allCandidateKeys.add(k);
          }
        });
      });
      specRows = Array.from(allCandidateKeys).slice(0, 5).map(k => ({
        label: k.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase()),
        get: c => c.specs?.[k]
      }));
    }

    // CRITICAL FILTER: Never render rows where EVERY candidate's value is invalid, empty, or "unknown"
    specRows = specRows.filter(row => candidates.some(c => hasValidSpec(row.get(c))));

    const table = document.createElement("table");
    table.className = "comparison-table";
    table.innerHTML = `
      <thead>
        <tr>
          <th>Attribute</th>
          ${candidates.map(c => `<th>${c.title} ${topRec && c.sku === topRec.sku ? '<span class="badge badge-green">Recommended</span>' : ''}</th>`).join("")}
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>Provider Source</td>
          ${candidates.map(c => `<td><span class="provider-pill ${c.provider_id === 'provider_alpha' ? 'pill-alpha' : 'pill-beta'}">${c.provenance}</span></td>`).join("")}
        </tr>
        <tr>
          <td>Price</td>
          ${candidates.map(c => `<td><strong>₹${Number(c.price).toLocaleString('en-IN')}</strong></td>`).join("")}
        </tr>
        ${specRows.map(row => `
          <tr>
            <td>${row.label}</td>
            ${candidates.map(c => {
              const val = row.get(c);
              return `<td>${hasValidSpec(val) ? val : "N/A"}</td>`;
            }).join("")}
          </tr>
        `).join("")}
      </tbody>
    `;
    comparisonContainer.appendChild(table);

    // Switch to comparison tab automatically
    const compBtn = document.querySelector('.tab-btn[data-tab="comparison"]');
    if (compBtn) compBtn.click();
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
      const itemTitle = currentTask?.top_recommendation?.title || "selected product";
      addTraceStep(9, "Dispatcher Agent", "Workflow Completed Safely", `Recommended item ("${itemTitle}") added to cart. Execution halted prior to checkout boundary as instructed.`, "completed");

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
