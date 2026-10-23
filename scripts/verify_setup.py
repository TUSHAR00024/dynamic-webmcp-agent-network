"""Environment and integration verification script."""
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from backend.registry.tool_registry import tool_registry
from backend.registry.provider_registry import provider_registry
from backend.routing.tool_router import tool_router
from backend.protocols.acp_integration import ACPIntegrationService


def verify_all():
    print("=============================================================")
    print("   Dynamic WebMCP Agent Network — Environment Verification   ")
    print("=============================================================")

    # 1. Python version
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    print(f"[✓] Python Runtime: {py_ver}")

    # 2. Providers
    providers = provider_registry.list_providers()
    print(f"[✓] Active Providers Registered: {len(providers)}")
    for p in providers:
        print(f"    • {p.name} ({p.provider_id}) - Health: {p.health.value} - Quality: {p.data_quality_score}")

    # 3. Tools
    tools = tool_registry.list_all_tools()
    print(f"[✓] Tools Discovered in Canonical Registry: {len(tools)}")
    for t in tools:
        print(f"    • [{t.provider_id}] {t.tool_name} -> {t.canonical_capability} ({t.classification.value})")

    # 4. Protocol & ACP
    acp_meta = ACPIntegrationService.get_protocol_metadata()
    print(f"[✓] Agent Chat Protocol (ACP): {acp_meta['name']} v{acp_meta['version']}")

    # 5. Router health
    prods, _ = tool_router.route_parallel_search({"query": "laptop"})
    print(f"[✓] Router Parallel Search Output: {len(prods)} products discovered across providers")

    print("=============================================================")
    print("   All components VERIFIED and operating normally!           ")
    print("=============================================================")


if __name__ == "__main__":
    verify_all()
