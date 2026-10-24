#!/usr/bin/env python3
"""Live integration self-check utility for ASI:One, Agentverse, and uAgent setup."""
import os
import sys
from pathlib import Path

# Add project root to path
BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from dotenv import load_dotenv
load_dotenv()

from backend.llm.asi1_client import asi1_client
from backend.uagent_app import agent, validate_agent_config


def run_live_check():
    print("=============================================================")
    print("   Dynamic WebMCP Agent Network — Live Path Health Check     ")
    print("=============================================================")

    # 1. Agent Configuration
    print(f"[✓] Agent Name:    {agent.name}")
    print(f"[✓] Agent Address: {agent.address}")

    seed_present = bool(os.getenv("AGENT_SEED_PHRASE", "").strip())
    use_mailbox = os.getenv("USE_AGENTVERSE", "false").lower() in ("true", "1", "yes")

    if seed_present:
        print("[✓] Seed Status:   Configured via AGENT_SEED_PHRASE")
    else:
        print("[!] Seed Status:   Using temporary ephemeral seed (Local testing only)")

    if use_mailbox:
        print("[✓] Mailbox Mode:  ENABLED (USE_AGENTVERSE=true)")
        mailbox_key = os.getenv("AGENTVERSE_MAILBOX_KEY", "").strip()
        if mailbox_key:
            print("[✓] Mailbox Key:   Present (secret preserved)")
        else:
            print("[!] Mailbox Key:   NOT set in .env (Needed for Agentverse mailbox)")
    else:
        print("[i] Mailbox Mode:  DISABLED (Local direct execution mode)")

    # 2. ASI1 LLM Connectivity Check
    asi1_key = os.getenv("ASI1_API_KEY", "").strip()
    if asi1_key:
        print("\n[Testing ASI1 LLM Connectivity...]")
        try:
            plan = asi1_client.extract_intent_and_constraints("Test: Find a laptop under 50000")
            print(f"[✓] ASI1 Connectivity: SUCCESS (Model: {asi1_client.model}, Plan query: '{plan.query}')")
        except Exception as e:
            print(f"[!] ASI1 Connectivity: FAILED ({e}). Deterministic fallback remains active.")
    else:
        print("\n[i] ASI1_API_KEY is not configured in .env -> [SKIPPED live call; deterministic fallback is active]")

    # 3. Agent Inspector Reminders
    print("\n=============================================================")
    print("   Human Instructions for Agentverse & ASI:One Inspector     ")
    print("=============================================================")
    print("1. Start the agent:  make agent")
    print("2. Open Agentverse:  https://agentverse.ai -> Local Agents")
    print(f"3. Register Address: {agent.address}")
    print("4. Inspector Tab:    Monitor live incoming chat protocols & RPCs")
    print("5. Test from ASI:One: https://asi1.ai -> Query @dynamic_webmcp_operator")
    print("=============================================================")


if __name__ == "__main__":
    run_live_check()
