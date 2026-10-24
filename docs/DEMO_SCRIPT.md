# Dynamic WebMCP Agent Network — 3-to-5 Minute Demonstration Script

**Tagline:** "From brittle screen clicks and DOM scrapers to structured, dynamic tool networks."  
**Event:** Fetch-A-Thon 3.0 by Fetch.ai Innovation Lab  

---

### [0:00 – 0:45] Introduction & The Architectural Paradigm Shift
*(Visual: Slide or title screen showing Architecture Diagram and Innovation Lab badges)*

**Presenter:**
> "Hello judges and builders! Traditional browser automation agents rely on computer-use: taking screenshots, guessing brittle CSS selectors, and clicking coordinates. When a website redesigns its layout or changes its DOM classes, the agent breaks.
>
> We built **Dynamic WebMCP Agent Network** to solve this permanently. 
>
> Instead of scraping HTML, our system communicates directly with structured website tools exposed through **WebMCP** (`window.modelContext`) and **Remote MCP** servers. 
>
> But we went further: real websites use completely different tool names and schemas. Our system introduces a **Canonical Capability Layer** that dynamically discovers, translates, and routes requests across heterogeneous providers at runtime, complete with multi-factor scoring, automatic failover, and strict cryptographic human-in-the-loop approval gates.
>
> Best of all: it is a real Fetch.ai uAgent integrated with the **Agent Chat Protocol (ACP v0.3.0)**, allowing users to interact directly through **ASI:One** without needing to open a browser."

---

### [0:45 – 2:15] Primary Workflow: Conversational ASI:One Chat & Interactive Cards
*(Visual: ASI:One chat window or running `make e2e` simulation)*

**Presenter:**
> "Let's demonstrate our primary interface inside an ASI:One chat conversation.
>
> We open a chat with `@dynamic_webmcp_operator` and provide our real-world shopping goal:
>
> *'Find the best laptop under ₹70,000 for programming and college. Search multiple websites, compare at least three suitable options, explain the trade-offs, and add the best option to my cart. Do not check out.'*
>
> Notice what happens behind the scenes:
> 1. Our **Planner Agent** leverages the **ASI1 LLM Reasoner** (`api.asi1.ai`) to extract structured constraints: category is laptops, budget ceiling is ₹70,000, and primary priorities are coding performance and battery longevity.
> 2. The **Dynamic Tool Router** identifies two active providers offering the `PRODUCT_SEARCH` capability:
>    - **Provider Alpha (TechMart Online)**: exposing `search_products(query, max_price)` via WebMCP.
>    - **Provider Beta (ElectroStore Pro)**: exposing `find_items(keywords, budget)` via Remote MCP.
> 3. The **Schema Normalizer** translates the single query into each retailer's native input schema and queries both in parallel.
> 4. The **Comparison Agent** compiles the results and returns an informative Markdown Decision Matrix along with an **Agent-Driven Interactive Card**.
>
> Look at the clear trade-off rationale: Lenovo ThinkPad E14 Gen 5 is ranked as our top recommendation due to its 8-core AMD Ryzen 7 processor and long battery life, outranking the ASUS Vivobook and HP Pavilion for our coding criteria.
>
> Now observe the **Policy Approval Gate**:
> Adding an item to a shopping cart is a state-changing action. Our system strictly refuses to execute without human authorization. It issues a short-lived approval token (`appr_xxxx`) bound to the exact SKU, price (₹62,990), and provider.
>
> In ASI:One, we can click the primary button on the **Review Card**, or simply reply:
> `APPROVE appr_xxxx`
>
> The agent validates that the token hasn't expired, performs an authoritative **zero-tolerance price drift re-check** against the live store, invokes the cart addition tool, and immediately executes an independent `CART_READ` query to verify that the cart state in the database actually holds the item.
>
> Finally, notice the **Checkout Boundary Safeguard**: the agent confirms item placement and immediately halts. It will never submit payment or complete checkout autonomously."

---

### [2:15 – 3:15] Companion WebMCP Store & Live Tool Discovery
*(Visual: Browser showing `http://localhost:8000`)*

**Presenter:**
> "To demonstrate how website tools are discovered on the client side, we built a companion demo web store.
>
> In the **⚡ Live WebMCP Registry** tab, you can inspect the tools registered directly onto `window.modelContext` by the retailer page.
>
> When an agent wants to interact with a WebMCP-enabled tab, calls are tunneled through our secure **Browser Bridge**.
>
> Security is non-negotiable: our bridge enforces an **Exact Hostname Allowlist**. If an attacker attempts domain spoofing using `evil-localhost.com:8000`, the connection is immediately rejected.
>
> And in the **Execution Trace** tab, you can observe every agent action logged in real-time with correlation IDs and execution timestamps."

---

### [3:15 – 4:00] Automatic Failover & Bonus Multi-Agent Bureau
*(Visual: Running `make test` or displaying `backend/bureau_network.py`)*

**Presenter:**
> "In real-world networks, providers fail. How does our network handle it?
>
> We introduced **Provider Gamma (FaultyStore)**, which simulates a 503 Service Unavailable error.
>
> When the router attempts to query Gamma, the **Fallback Manager** intercepts the failure, logs the incident to the audit trail, and instantly fails over to Provider Alpha without aborting the user's task.
>
> Furthermore, for bonus multi-agent collaboration, we architected a native **Fetch.ai Bureau Network** in `backend/bureau_network.py`.
>
> Here, five specialist agents—Research Specialist, Comparison Specialist, Policy Specialist, Cart Specialist, and Network Supervisor—run as distinct `uagents.Agent` instances inside a `uagents.Bureau`, exchanging strongly typed Pydantic `Model` messages across their unique cryptographic Bech32 addresses."

---

### [4:00 – 4:30] Summary & Submission Verification
*(Visual: Terminal running `make test` and `make verify`)*

**Presenter:**
> "To summarize:
> - **25 automated unit and regression tests** pass in under 0.02 seconds (`make test`).
> - A 4-turn **end-to-end conversation simulation** tests the full ACP lifecycle (`make e2e`).
> - Powered by real Fetch.ai `uagents` (v0.26.1) and Agent Chat Protocol v0.3.0.
> - Discoverable on Agentverse and operable in ASI:One with Interactive Cards.
>
> The Dynamic WebMCP Agent Network transforms the web from a collection of fragile HTML pages into a reliable, structured, permission-aware tool network for autonomous AI agents.
>
> Thank you!"
