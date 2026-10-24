# DEVPOST SUBMISSION OVERVIEW

## Project Name
**Dynamic WebMCP Agent Network**

## Tagline
From brittle screen clicks and DOM scrapers to structured, dynamic tool networks.

---

## Inspiration
Autonomous web agents are the future of digital assistance, but existing "computer-use" agents are fundamentally brittle. They take screenshots, guess CSS selectors, and simulate mouse clicks on raw pixels. Whenever a retailer redesigns a button class or tweaks a modal layout, these agents break immediately.

We asked: *What if websites exposed structured, typed tools directly to AI agents using emerging standards like WebMCP (`window.modelContext`), and what if a decentralized multi-agent network could dynamically discover, normalize, rank, and execute these tools with cryptographic user authorization?*

Built for **Fetch-A-Thon 3.0 by Fetch.ai Innovation Lab**, Dynamic WebMCP Agent Network turns this vision into reality.

---

## What It Does
Dynamic WebMCP Agent Network is a decentralized multi-agent system that allows users to express complex, high-consequence goals in natural language (e.g., *"Find the best laptop under ₹70,000 for coding and college. Compare options across multiple stores, explain trade-offs, and add the best option to my cart. Do not check out."*).

Key features:
1. **Dynamic Runtime Discovery**: Discovers tools exposed on active browser tabs (WebMCP) and remote servers (MCP) on-the-fly without hardcoded schemas.
2. **Canonical Capability Normalization**: Automatically bridges divergent retailer APIs (e.g., mapping TechMart's `search_products(query, max_price)` and ElectroStore's `find_items(keywords, budget)` into canonical `PRODUCT_SEARCH`).
3. **Multi-Factor Provider Ranking**: Evaluates providers using an objective multi-factor scoring algorithm balancing schema fitness, data quality, historical uptime, and latency.
4. **Resilient Automatic Failover**: Intercepts provider outages (e.g. simulated 503 errors) and re-routes tasks seamlessly to healthy alternatives.
5. **Cryptographic Approval Gate**: Generates HMAC-SHA256 bound tokens with a 300s TTL for state-changing cart additions. Zero execution occurs without explicit user authorization.
6. **Zero-Tolerance Price Drift Verification**: Authoritatively re-checks live catalog prices immediately prior to execution, revoking approvals if prices fluctuate.
7. **Independent Postcondition Verification**: Independently inspects cart database state via `CART_READ` queries rather than blindly trusting return codes.
8. **Enforced Checkout Boundary**: Terminates execution before payment or checkout, safeguarding user funds.
9. **Dual-Mode Experience**:
   - **Primary Interface**: Operates 100% inside **ASI:One chat** using the official **Fetch.ai Agent Chat Protocol (ACP v0.3.0)** and native **Agentverse Interactive Cards**.
   - **Companion Web Store**: An interactive web application demonstrating browser-side tool discovery and real-time execution trace streaming.

---

## How We Built It
- **Agent Architecture**: Built with the official Fetch.ai `uagents` SDK (v0.26.1) and `uagents_core.contrib.protocols.chat`.
- **Reasoning Engine**: Powered by **ASI1 LLM** (`api.asi1.ai`) with a robust deterministic fallback for intent extraction and trade-off rationalization.
- **Protocol Standards**: Implements ACP v0.3.0 (`ChatMessage`, `StartSessionContent`, `TextContent`, `MetadataContent`) with Agentverse-compliant interactive cards (`card_kind: "review"`, `"carousel"`).
- **Multi-Agent Bureau**: Configured a native `uagents.Bureau` coordinating 5 discrete specialist agents (Research, Comparison, Policy, Cart, Supervisor) exchanging typed Pydantic `Model` messages across cryptographic Bech32 addresses (`agent1q...`).
- **WebMCP Integration**: Implements the W3C Web Machine Learning Community Group `window.modelContext` standard on the frontend with a secure tunneling browser bridge.
- **Security Engineering**: Developed exact hostname allowlists preventing DNS rebinding, prompt-injection sanitizers, cryptographic sender binding, and idempotency guards against replay attacks.

---

## Challenges We Ran Into
- **Divergent Retailer Schemas**: No two e-commerce sites format product specs or cart tools identically. We designed a bidirectional schema normalizer mapping between canonical models and provider payloads with strict runtime validation.
- **Bridging Browser Tabs with Headless uAgents**: ASI:One operates in the cloud and cannot directly inspect client browser tabs. We solved this with a dual-mode architecture: the primary workflow executes server-side via the unified workflow engine directly in ASI:One chat, while the companion web store communicates via a secure WebSocket/HTTP bridge.
- **Safe Action Execution**: Preventing race conditions and price surges required an authoritative re-check of product details right before cart execution, guaranteeing that user approvals cannot be exploited if prices surge.

---

## Accomplishments That We're Proud Of
- **Zero Fluff, 100% Verified**: 25 automated unit and regression tests pass in under 0.02 seconds (`make test`).
- **Complete ASI:One Chat Flow**: Full 4-turn E2E conversational simulation (`make e2e`) verifying start session, multi-provider search, human approval, and replay interception.
- **Native Fetch.ai Technology**: Genuine `uagents.Agent` with Mailbox integration and official Agent Chat Protocol v0.3.0.
- **Interactive UI Cards**: Rich Agentverse review and carousel cards rendered directly in chat sessions.

---

## What We Learned
- Structured tool discovery via WebMCP is drastically faster, more reliable, and more token-efficient than vision-based or DOM-scraping automation.
- Independent postcondition verification (`CART_READ`) is essential for autonomous agents to confirm real-world state changes beyond superficial HTTP status codes.

---

## What's Next
- Deploying the multi-agent network on Agentverse and publishing to the ASI:One Agent Explorer.
- Expanding beyond shopping into airline flight reservations, medical appointment scheduling, and automated procurement.
- Integrating native micropayments using Fetch.ai's on-chain settlement rails for premium sourcing dossiers.

---

## Built With
- `python` (3.11)
- `uagents` (0.26.1)
- `uagents-core` (0.4.12)
- `Agent Chat Protocol (ACP v0.3.0)`
- `ASI:One & ASI1 LLM`
- `Agentverse Mailbox`
- `WebMCP / modelContext API`
- `cosmpy`
- `pydantic`
