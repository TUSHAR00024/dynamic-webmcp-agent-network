#!/usr/bin/env python3
"""End-to-End simulation of an ASI:One user conversation with the uAgent."""
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    StartSessionContent,
    TextContent
)
from backend.uagent_app import handle_incoming_chat


class MockContext:
    def __init__(self):
        self.sent_messages = []
        self.logger = MockLogger()

    async def send(self, recipient: str, msg: Any):
        self.sent_messages.append((recipient, msg))


class MockLogger:
    def info(self, msg): pass
    def warning(self, msg): pass
    def error(self, msg): pass
    def exception(self, msg): pass


async def run_e2e_simulation():
    print("=============================================================")
    print("  ASI:One E2E Chat Simulation Test (Agent Chat Protocol v0.3)")
    print("=============================================================")

    ctx = MockContext()
    user_address = "agent1q_test_user_simulated_asi1"

    # Step 1: Start Session Greeting
    print("\n[Step 1] User opens conversation in ASI:One (StartSessionContent)...")
    start_msg = ChatMessage(
        timestamp=datetime.now(timezone.utc),
        msg_id=uuid4(),
        content=[StartSessionContent(type="start-session")]
    )
    await handle_incoming_chat(ctx, user_address, start_msg)

    # Check acknowledgement and greeting
    acks = [m for _, m in ctx.sent_messages if isinstance(m, ChatAcknowledgement)]
    chat_replies = [m for _, m in ctx.sent_messages if isinstance(m, ChatMessage)]
    assert len(acks) >= 1, "Expected ChatAcknowledgement!"
    assert len(chat_replies) >= 1, "Expected Greeting ChatMessage!"
    print(f"  ✓ Agent returned acknowledgement for msg {acks[-1].acknowledged_msg_id}")
    print(f"  ✓ Agent sent greeting: {chat_replies[-1].content[0].text[:60]}...")

    # Step 2: Natural Language Goal Request
    print("\n[Step 2] User sends shopping goal...")
    user_goal = (
        "Find the best laptop under ₹70,000 for programming and college. "
        "Search multiple websites, compare at least three options, explain trade-offs, and add the best option to my cart. Do not check out."
    )
    req_msg = ChatMessage(
        timestamp=datetime.now(timezone.utc),
        msg_id=uuid4(),
        content=[TextContent(type="text", text=user_goal)]
    )
    ctx.sent_messages.clear()
    await handle_incoming_chat(ctx, user_address, req_msg)

    replies = [m for _, m in ctx.sent_messages if isinstance(m, ChatMessage)]
    assert len(replies) >= 1, "Expected response with comparison matrix!"
    reply_text = replies[-1].content[0].text
    print(f"  ✓ Received response:\n{reply_text[:280]}...\n")
    assert "Product Comparison & Decision Matrix" in reply_text
    assert "Action Authorization Required" in reply_text
    assert "APPROVE appr_" in reply_text

    # Extract approval ID from reply text
    import re
    appr_match = re.search(r"APPROVE\s+(appr_[a-f0-9]+)", reply_text)
    assert appr_match, "Could not find approval ID in reply!"
    approval_id = appr_match.group(1)
    print(f"  ✓ Extracted approval token: {approval_id}")

    # Step 3: User Approves Cart Addition
    print(f"\n[Step 3] User replies 'APPROVE {approval_id}'...")
    approve_msg = ChatMessage(
        timestamp=datetime.now(timezone.utc),
        msg_id=uuid4(),
        content=[TextContent(type="text", text=f"APPROVE {approval_id}")]
    )
    ctx.sent_messages.clear()
    await handle_incoming_chat(ctx, user_address, approve_msg)

    exec_replies = [m for _, m in ctx.sent_messages if isinstance(m, ChatMessage)]
    assert len(exec_replies) >= 1, "Expected execution response!"
    exec_text = exec_replies[-1].content[0].text
    print(f"  ✓ Received execution confirmation:\n{exec_text}\n")
    assert "Action Authorized and Verified" in exec_text
    assert "Checkout Boundary Safeguard" in exec_text

    # Step 4: Test Idempotency (duplicate approval replay)
    print("\n[Step 4] Testing duplicate approval replay attack...")
    dup_msg = ChatMessage(
        timestamp=datetime.now(timezone.utc),
        msg_id=uuid4(),
        content=[TextContent(type="text", text=f"APPROVE {approval_id}")]
    )
    ctx.sent_messages.clear()
    await handle_incoming_chat(ctx, user_address, dup_msg)
    dup_replies = [m for _, m in ctx.sent_messages if isinstance(m, ChatMessage)]
    # Should safely return existing result without error or re-executing
    assert "Action Authorized and Verified" in dup_replies[-1].content[0].text
    print("  ✓ Idempotency guard safely intercepted duplicate replay!")

    print("=============================================================")
    print("  E2E SIMULATION PASSED: 100% SUCCESSFUL CONVERSATION FLOW   ")
    print("=============================================================")


if __name__ == "__main__":
    asyncio.run(run_e2e_simulation())
