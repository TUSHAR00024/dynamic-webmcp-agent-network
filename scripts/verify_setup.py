"""Environment, protocol, and tool capability verification script with active assertions."""
import os
import sys
from pathlib import Path

# Add project root to path
BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from dotenv import load_dotenv
load_dotenv()

from uagents import Agent
from uagents_core.contrib.protocols.chat import chat_protocol_spec

from backend.registry.capability_map import CanonicalCapability
from backend.registry.tool_registry import tool_registry
from backend.registry.provider_registry import provider_registry
from backend.routing.tool_router import tool_router
from backend.protocols.acp_integration import ACPIntegrationService


def verify_all() -> bool:
    print("=============================================================")
    print("   Dynamic WebMCP Agent Network — Environment Verification   ")
    print("=============================================================")
    failures = []

    # 1. Python version assertion
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if sys.version_info.major < 3 or (sys.version_info.major == 3 and sys.version_info.minor < 10):
        failures.append(f"Python 3.10+ required. Found {py_ver}")
        print(f"[✗] Python Runtime: {py_ver} (Requires >= 3.10)")
    else:
        print(f"[✓] Python Runtime: {py_ver} (>= 3.10)")

    # 2. Agent Address Derivation
    seed = os.getenv("AGENT_SEED_PHRASE")
    if not seed:
        seed = "verify test offline temporary seed phrase only for verification run"
        seed_label = "(derived using local fallback seed; set AGENT_SEED_PHRASE for Agentverse)"
    else:
        seed_label = "(derived from AGENT_SEED_PHRASE in .env)"

    try:
        import asyncio
        try:
            asyncio.get_event_loop()
        except RuntimeError:
            asyncio.set_event_loop(asyncio.new_event_loop())

        from uagents.crypto import Identity
        identity = Identity.from_seed(seed, 0)
        addr = str(identity.address)
        assert addr.startswith("agent1"), f"Invalid agent address format: {addr}"
        assert len(addr) == 65, f"Expected 65-char bech32 address, got {len(addr)}"
        print(f"[✓] Agent Address Derivation: {addr[:16]}...{addr[-6:]} {seed_label}")
    except Exception as e:
        failures.append(f"Agent address derivation failed: {e}")
        print(f"[✗] Agent Address Derivation: FAILED ({e})")

    # 3. Chat Protocol Spec (ACP)
    try:
        digest = chat_protocol_spec.digest
        assert digest and digest.startswith("proto:"), f"Invalid protocol digest: {digest}"
        acp_meta = ACPIntegrationService.get_protocol_metadata()
        print(f"[✓] Agent Chat Protocol (ACP): {acp_meta['name']} (digest: {digest[:22]}...)")
    except Exception as e:
        failures.append(f"Chat protocol specification failed: {e}")
        print(f"[✗] Agent Chat Protocol: FAILED ({e})")

    # 4. Providers Registration
    providers = provider_registry.list_providers()
    if len(providers) < 2:
        failures.append(f"Expected at least 2 registered providers, found {len(providers)}")
        print(f"[✗] Active Providers: {len(providers)} (minimum 2 required)")
    else:
        print(f"[✓] Active Providers Registered: {len(providers)}")
        for p in providers:
            print(f"    • {p.name} ({p.provider_id}) - Health: {p.health.value} - Quality: {p.data_quality_score}")

    # 5. Core Capability Coverage
    core_capabilities = [
        CanonicalCapability.PRODUCT_SEARCH,
        CanonicalCapability.PRODUCT_DETAILS,
        CanonicalCapability.CART_ADD,
        CanonicalCapability.CART_READ,
    ]
    all_tools = tool_registry.list_all_tools()
    print(f"[✓] Tools Discovered in Canonical Registry: {len(all_tools)}")

    missing_caps = []
    for cap in core_capabilities:
        matched = tool_registry.find_tools(cap, active_only=True)
        cap_name = cap if isinstance(cap, str) else getattr(cap, "value", str(cap))
        if not matched:
            missing_caps.append(cap_name)
        else:
            providers_offering = {t.provider_id for t in matched}
            print(f"    • {cap_name}: available from {', '.join(sorted(providers_offering))}")

    if missing_caps:
        failures.append(f"Missing active providers for capabilities: {', '.join(missing_caps)}")
        print(f"[✗] Capability Coverage: Missing providers for {missing_caps}")
    else:
        print(f"[✓] Core Capability Coverage: All {len(core_capabilities)} capabilities actively mapped")

    # 6. ASI1 API Key Check
    asi_key = os.getenv("ASI1_API_KEY", "").strip()
    if asi_key:
        print(f"[✓] ASI1 Reasoning Engine: CONFIGURED (Model: asi1, live LLM active)")
    else:
        print(f"[-] ASI1 Reasoning Engine: SKIPPED (No ASI1_API_KEY; deterministic regex fallback active)")

    # 7. Router Parallel Execution
    try:
        prods, audit = tool_router.route_parallel_search({"query": "laptop"})
        assert len(prods) > 0, "Router returned 0 products for query 'laptop'"
        print(f"[✓] Router Parallel Search: {len(prods)} products discovered across providers")
    except Exception as e:
        failures.append(f"Router parallel search failed: {e}")
        print(f"[✗] Router Parallel Search: FAILED ({e})")

    print("=============================================================")
    if failures:
        print(f"   VERIFICATION FAILED: {len(failures)} issue(s) detected:")
        for f in failures:
            print(f"   - {f}")
        print("=============================================================")
        return False
    else:
        print("   All components VERIFIED and operating normally!           ")
        print("=============================================================")
        return True


if __name__ == "__main__":
    success = verify_all()
    sys.exit(0 if success else 1)
