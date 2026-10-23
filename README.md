# Dynamic WebMCP Agent Network
### Autonomous Multi-Agent Web Operator using WebMCP + Fetch.ai + ACP + ASI:One
**Fetch-A-Thon 3.0 by Fetch.ai Innovation Lab**

> *"From brittle screen clicks to structured, dynamic tool networks."*

---

## 1. Executive Summary & Problem Statement

Traditional web AI agents frequently rely on computer-use approaches: taking screenshots, guessing CSS selectors, and clicking coordinates. When website layouts or front-end DOMs change, these agents break.

**Dynamic WebMCP Agent Network** takes an entirely different, future-proof approach:
- Websites expose structured tools through **WebMCP** (`navigator.modelContext` / `window.modelContext`) and **Remote MCP** servers.
- Specialist agents dynamically discover available website tools at runtime without hardcoded schemas.
- A **Canonical Capability Layer** (`PRODUCT_SEARCH`, `CART_ADD`) normalizes divergent tool names and parameters (`search_products` vs `find_items`, `add_to_cart` vs `cart_add`).
- The **Dynamic Tool Router** scores candidate providers using a multi-factor ranking function, executes parallel multi-site research, handles automatic failover/recovery, and enforces a strict **human-in-the-loop approval gate** with independent postcondition verification before mutating shopping cart state.
- Fully integrated with Fetch.ai's **Agent Chat Protocol (ACP)** and discoverable on **ASI:One** and **Agentverse**.

---

## 2. System Architecture

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
                   | Provider Alpha (TechMart)  |  | Provider Beta (ElectroStore)
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

## 3. Dynamic Tool Routing Graph

```text
User Request: "Find laptop under ₹70,000 for coding, compare 3 options, add best to cart. Do not check out."
   |
   |-- 1. Planner Agent: Extracts constraints (Budget: 70000, Priorities: [coding, battery, reliability])
   |-- 2. Discovery Agent: Scans active providers -> Discovers Alpha (WebMCP) and Beta (Remote MCP)
   |-- 3. Dynamic Router: Ranks providers and executes parallel search:
   |      |--> Provider Alpha: `search_products(query="laptop", max_price=70000)`
   |      |--> Provider Beta:  `find_items(keywords="laptop", budget=70000)`
   |-- 4. Schema Normalizer: Normalizes heterogeneous records into canonical `ProductRecord`
   |-- 5. Comparison Agent: Scores options -> Recommends ThinkPad E14 Gen 5 (Score: 93/100)
   |-- 6. Policy Agent: Halts execution; issues SHA-256 bound approval token (300s TTL)
   |-- 7. Human Operator: Clicks "Authorize & Execute"
   |-- 8. Cart Action Agent: Invokes Alpha's `add_to_cart(session_id, "alpha_thinkpad_e14", 1)`
   |-- 9. Postcondition Verifier: Reads `get_cart()` to independently confirm item presence in database
   |-- 10. Dispatcher Agent: Returns verified result; checkout boundary strictly maintained
```

---

## 4. Multi-Agent Specialist Responsibilities

| Agent | Responsibility | Message Envelopes |
| :--- | :--- | :--- |
| **`dispatcher_agent`** | Primary user gateway; manages ACP conversation thread and ASI:One responses. | `ChatMessage`, `ChatAcknowledgement` |
| **`planner_agent`** | Deconstructs user intent into structured constraints and required capabilities. | `TaskPlanRequest`, `TaskPlanResponse` |
| **`discovery_agent`** | Discovers tools exposed by active browser WebMCP pages and remote MCP servers. | `DiscoveryQueryMessage`, `DiscoveryResultMessage` |
| **`routing_agent`** | Evaluates provider eligibility, computes multi-factor rankings, and manages fallback. | `RoutingDecisionRecord` |
| **`research_agent`** | Dispatches parallel catalog queries and aggregates candidate records. | `ResearchQueryMessage`, `ResearchResultMessage` |
| **`comparison_agent`** | Ranks candidates against multi-criteria constraints, detailing trade-offs. | `ComparisonRequestMessage`, `ComparisonResultMessage` |
| **`policy_agent`** | Classifies action severity, issues cryptographically bound approval tokens. | `PolicyApprovalRequestMessage` |
| **`cart_agent`** | Executes approved mutations; prevents duplicate execution via idempotency keys. | `ActionExecutionMessage`, `ActionVerificationResultMessage` |
| **`audit_agent`** | Logs verifiable execution traces with start/finish timestamps and redacts secrets. | `AuditEvent` |

---

## 5. Canonical Capabilities & Schema Normalization

In real-world e-commerce, tools differ drastically across retailers:
- **Provider Alpha (TechMart Online)**: `search_products(query, max_price)`, `add_to_cart(session_id, product_id, quantity)`
- **Provider Beta (ElectroStore Pro)**: `find_items(keywords, budget)`, `cart_add(session_id, item_sku, count)`
- **Provider Gamma (FaultyStore Global)**: `catalog_search(filter_dict)` (Simulates 503 error for resilience testing)

The **Schema Normalizer** performs two-way translation:
1. Translates canonical requests (`PRODUCT_SEARCH`, `CART_ADD`) into the provider's exact parameter schema.
2. Normalizes divergent output records into unified canonical models (`ProductRecord`).

---

## 6. Provider Ranking & Multi-Factor Scoring

When a capability is requested, the router evaluates candidate providers using normalized weights:

$$\text{Score} = 0.35 \cdot S_{\text{match}} + 0.25 \cdot S_{\text{quality}} + 0.20 \cdot S_{\text{reliability}} + 0.10 \cdot S_{\text{freshness}} - 0.10 \cdot P_{\text{latency}} - 0.0 \cdot P_{\text{cost}}$$

Hard constraints (e.g., maximum budget, required cart capability) are filtered **before** scoring. A high reliability score never overrides an incompatible tool schema or missing parameter.

---

## 7. WebMCP vs Remote MCP

| Dimension | Browser WebMCP | Remote MCP |
| :--- | :--- | :--- |
| **Execution Context** | Client-side web page / browser tab | External process / remote server |
| **Discovery Mechanism** | `navigator.modelContext.getTools()` | MCP initialization handshake (`tools/list`) |
| **State Scope** | User session, active cookies, DOM state | Backend database, remote services |
| **Bridge Required** | **Yes** — Bridge tunnels calls into tab | **No** — Direct network RPC connection |

---

## 8. Technology Stack

- **Backend & Router**: Python 3.11, SQLite WAL persistence, standard library concurrency (`concurrent.futures`), zero external pip dependencies required for core demo.
- **Agent Framework**: Fetch.ai `uagents` SDK, `uagents_core.contrib.protocols.chat` (ACP v0.3.0).
- **WebMCP**: W3C Web Machine Learning Community Group `modelContext` API.
- **Frontend**: Modern HTML5, CSS3 Custom Properties, Modular ES6 JavaScript.

---

## 9. File Structure

```text
dynamic-webmcp-agent-network/
├── README.md
├── LICENSE
├── Makefile
├── pyproject.toml
├── requirements.txt
├── .env.example
├── .gitignore
├── apps/
│   └── demo-store/
│       ├── index.html                  # Responsive SaaS UI with catalog, registry & agent trace
│       ├── styles.css                  # Modern dark-mode design system
│       ├── app.js                      # Reactive frontend application controller
│       └── webmcpCompatibility.js      # W3C WebML CG modelContext polyfill & tool registration
├── backend/
│   ├── app.py                          # Unified HTTP server & WebMCP bridge listener
│   ├── models/
│   │   ├── tool.py                     # ToolDefinition, ToolClassification, ExecutionMode
│   │   ├── product.py                  # Canonical ProductRecord, ProductSpecs, CartStateRecord
│   │   ├── provider.py                 # ProviderInfo, ProviderHealth, ProviderScoreBreakdown
│   │   ├── task.py                     # Task, TaskStep, WorkflowState, UserConstraints
│   │   └── audit_event.py              # RoutingDecisionRecord, AuditEvent
│   ├── registry/
│   │   ├── capability_map.py           # Canonical capabilities definitions & constraints
│   │   ├── schema_normalizer.py        # Two-way translation between canonical & provider schemas
│   │   ├── tool_registry.py            # Dynamic in-memory registry & capability indexing
│   │   ├── provider_registry.py        # Active provider registry & health tracking
│   │   └── discovery_cache.py          # TTL caching and cache invalidation
│   ├── adapters/
│   │   ├── base_adapter.py             # Abstract Base Class for provider tool adapters
│   │   ├── demo_provider_adapter.py    # Alpha (WebMCP), Beta (Remote MCP), Gamma (Faulty)
│   │   └── webmcp_adapter.py           # Live browser context execution adapter
│   ├── routing/
│   │   ├── provider_ranker.py          # Multi-factor scoring function
│   │   ├── routing_policy.py           # Hard constraint checking & exclusion logging
│   │   ├── fallback_manager.py         # Automatic failover on provider failure
│   │   ├── parallel_executor.py        # ThreadPool concurrent multi-provider search
│   │   └── tool_router.py              # Master dynamic tool router
│   ├── bridge/
│   │   ├── browser_bridge.py           # Active browser tab tracker & execution tunnel
│   │   ├── bridge_protocol.py          # Bridge message schemas
│   │   └── bridge_security.py          # Origin allowlist & prompt injection sanitization
│   ├── agents/
│   │   ├── dispatcher_agent.py         # ACP / ASI:One master coordinator
│   │   ├── planner_agent.py            # Constraint and capability planner
│   │   ├── discovery_agent.py          # Dynamic tool discovery specialist
│   │   ├── research_agent.py           # Multi-provider product research specialist
│   │   ├── comparison_agent.py         # Multi-criteria comparison specialist
│   │   ├── policy_agent.py             # Human approval gate & token binding specialist
│   │   ├── cart_agent.py               # Verified cart action execution specialist
│   │   └── audit_agent.py              # Audit logging & privacy redaction specialist
│   ├── protocols/
│   │   ├── acp_integration.py          # Agent Chat Protocol (ACP) v0.3.0 models
│   │   ├── agentverse_config.py        # Agentverse manifest generator
│   │   └── messages.py                 # Inter-agent IPC envelopes
│   ├── safety/
│   │   └── idempotency.py              # Idempotency token guard
│   ├── services/
│   │   └── payment_service.py          # Fetch.ai Payment Protocol simulation adapter
│   └── tests/
│       ├── test_registry.py            # Tool registration, capability queries, invalidation
│       ├── test_schema_normalization.py# Input/output translation between Alpha & Beta
│       ├── test_provider_ranking.py    # Multi-factor ranking and health policy exclusions
│       ├── test_parallel_search.py     # Concurrent multi-provider search & automatic failover
│       ├── test_bridge_protocol.py     # Browser session registration & security sanitization
│       ├── test_agent_messages.py      # Agent orchestration & ACP response flow
│       └── run_phase2_tests.py         # Test discovery & execution suite
├── docs/
│   ├── ARCHITECTURE.md                 # System architecture & routing formulas
│   ├── WEBMCP_COMPATIBILITY.md         # WebMCP vs Remote MCP specification
│   ├── JUDGING_CRITERIA_CHECKLIST.md   # Mapping all 5 judging criteria to concrete evidence
│   ├── ACP_AGENTVERSE_SETUP.md         # Agentverse and ASI:One registration guide
│   └── DEMO_SCRIPT.md                  # Two-minute demonstration script
└── scripts/
    ├── verify_setup.py                 # Environment verification script
    └── run_demo.sh                     # Single-command launcher
```

---

## 10. Quickstart & How to Run

### Prerequisites
- Python 3.10+ (tested on Python 3.11)
- Modern web browser (Chrome, Edge, Safari, Firefox)

### 1. Verify Environment
```bash
python3 scripts/verify_setup.py
```

### 2. Run All Automated Unit Tests (19 tests)
```bash
python3 backend/tests/run_phase2_tests.py
```
*Expected Output:*
```text
Ran 19 tests in 0.006s. OK
```

### 3. Launch Demo Store and Agent Server
```bash
python3 backend/app.py
```
Open your browser to:
👉 **`http://127.0.0.1:8000`**

---

## 11. Testing Scenario Walkthrough

1. Open `http://127.0.0.1:8000` in your browser.
2. Observe the **Multi-Provider Catalog**: products from **Provider Alpha (TechMart)** and **Provider Beta (ElectroStore)** are displayed with live specs.
3. Switch to the **⚡ Live WebMCP Registry** tab: see all tools registered directly onto `window.modelContext`.
4. Click **Execute Multi-Agent Workflow** with the natural-language prompt:
   > *"Find the best laptop under ₹70,000 for programming and college. Search multiple websites, compare at least three suitable options, explain the trade-offs, and add the best option to my cart. Do not check out."*
5. Watch the **Execution Trace & Explainability** panel stream real-time steps:
   - **Planner Agent**: parsed constraints (Budget: ₹70,000, Priorities: coding, battery, reliability).
   - **Discovery Agent**: discovered active WebMCP and Remote MCP tools.
   - **Dynamic Tool Router**: normalized canonical query and dispatched parallel search across Alpha and Beta.
   - **Comparison Agent**: scored 8 candidate laptops and selected Lenovo ThinkPad E14 Gen 5 (Score: 93/100).
   - **Policy Agent**: halted execution and triggered the **Human Approval Gate Modal** with SHA-256 token binding.
6. Click **Authorize & Execute Action**:
   - The **Cart Action Agent** executes Alpha's `add_to_cart`.
   - The **Postcondition Verifier** independently queries Alpha's `get_cart()` to verify the item exists in the cart.
   - The cart drawer opens, displaying the verified item and total.
   - **Checkout Boundary**: Execution halts before checkout, safeguarding the user.

---

## 12. Judging Criteria Mapping

| Judging Category | Weight | Evaluated Capability | Evidence Reference |
| :--- | :---: | :--- | :--- |
| **Functionality & Implementation** | 25% | Multi-provider discovery, dynamic schema normalization, cart mutation, and postcondition verification. | `backend/routing/tool_router.py`<br>19 passing automated tests |
| **Fetch.ai Technology** | 20% | Agent Chat Protocol (ACP), Agentverse manifest, ASI:One compatibility. | `backend/protocols/acp_integration.py`<br>`backend/protocols/agentverse_config.py` |
| **Innovation** | 20% | Dynamic runtime discovery & canonical capabilities instead of hardcoded DOM scrapers. | `backend/registry/capability_map.py`<br>`backend/registry/schema_normalizer.py` |
| **Impact & Usefulness** | 20% | Real-world problem solving: cross-retailer automated hardware sourcing with transparent comparison. | `apps/demo-store/index.html`<br>`docs/WEBMCP_COMPATIBILITY.md` |
| **User Experience** | 15% | Natural-language interface, execution trace, comparison matrix, human approval modal. | `apps/demo-store/app.js`<br>`apps/demo-store/styles.css` |
| **Bonus Criteria** | Bonus | 9 specialized agents collaborating, automatic failover (Provider Gamma recovery), and Payment Protocol simulation. | `backend/agents/`<br>`backend/routing/fallback_manager.py`<br>`backend/services/payment_service.py` |

---

## 13. License

Released under the **MIT License**. See `LICENSE` for details.
