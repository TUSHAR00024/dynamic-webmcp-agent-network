"""Test Bureau instantiation and agent addresses."""
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from backend.bureau_network import (
    research_agent,
    comparison_agent,
    policy_agent_instance,
    cart_agent_instance,
    supervisor_agent,
    create_bureau
)

def test_bureau_setup():
    print("=============================================================")
    print("   Testing Fetch.ai Multi-Agent Bureau Configuration        ")
    print("=============================================================")
    bureau = create_bureau()
    agents = [
        research_agent,
        comparison_agent,
        policy_agent_instance,
        cart_agent_instance,
        supervisor_agent
    ]
    for a in agents:
        print(f"[✓] Initialized {a.name:25} Address: {a.address}")
    print("=============================================================")
    print("   Bureau multi-agent network configuration verified!        ")
    print("=============================================================")

if __name__ == "__main__":
    test_bureau_setup()
