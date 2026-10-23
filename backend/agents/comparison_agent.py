"""Comparison Specialist Agent: Ranks candidates and explains trade-offs."""
from typing import Any, Dict, List
from backend.protocols.messages import ComparisonRequestMessage, ComparisonResultMessage


class ComparisonAgent:
    def __init__(self):
        self.agent_name = "comparison_agent"

    def compare_candidates(self, msg: ComparisonRequestMessage) -> ComparisonResultMessage:
        ranked = []
        for p in msg.candidates:
            score = 65.0
            specs = p.get("specs", {})

            # Coding / CPU
            cpu = str(specs.get("cpu", "")).lower()
            if "ryzen 7" in cpu or "i5-13500h" in cpu or "12 cores" in cpu:
                score += 15.0
            elif "i5" in cpu:
                score += 10.0

            # Battery
            bat = str(specs.get("battery", "")).lower()
            if "75wh" in bat or "10.5" in bat:
                score += 10.0
            elif "57wh" in bat or "9.5" in bat:
                score += 8.0
            elif "unknown" in bat:
                score -= 5.0  # Transparent penalty for uncertainty

            # RAM & Storage
            if "16gb" in str(specs.get("ram", "")).lower():
                score += 5.0

            # Warranty
            if "3-year" in str(specs.get("warranty", "")).lower():
                score += 5.0

            ranked.append({
                "product": p,
                "composite_score": round(score, 1)
            })

        ranked.sort(key=lambda x: x["composite_score"], reverse=True)
        top = ranked[0]["product"] if ranked else None

        rationale = (
            f"Compared {len(ranked)} eligible options. Top pick '{top.get('title')}' ranked highest "
            f"due to superior CPU multi-core performance, proven battery life, and warranty support."
        ) if top else "No candidates met all hard constraints."

        return ComparisonResultMessage(
            correlation_id=msg.correlation_id,
            sender_agent=self.agent_name,
            target_agent="policy_agent",
            task_id=msg.task_id,
            ranked_candidates=[r["product"] for r in ranked],
            top_recommendation=top,
            rationale=rationale
        )


comparison_agent = ComparisonAgent()
