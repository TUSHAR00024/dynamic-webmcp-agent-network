#!/usr/bin/env python3
"""Generate a cryptographically secure seed phrase for a Fetch.ai uAgent."""
import secrets

def generate_seed(length: int = 48) -> str:
    return secrets.token_urlsafe(length)

if __name__ == "__main__":
    seed = generate_seed()
    print("Generated Agent Seed Phrase (keep private, set as AGENT_SEED_PHRASE in .env):")
    print(seed)
