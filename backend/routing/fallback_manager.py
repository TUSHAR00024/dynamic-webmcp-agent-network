"""Fallback and Failure Recovery Manager for Dynamic Tool Router."""
import logging
from typing import Any, Dict, List, Optional
from backend.models.tool import ToolExecutionResult

logger = logging.getLogger("Routing.FallbackManager")


class FallbackManager:
    @staticmethod
    def should_trigger_fallback(result: ToolExecutionResult) -> bool:
        """Evaluate if tool result signifies a retryable/recoverable failure."""
        return result.status == "FAILED"

    @staticmethod
    def select_fallback_provider(
        failed_provider_id: str,
        ranked_candidates: List[str]
    ) -> Optional[str]:
        """Pick the next best provider from ranked candidate list."""
        for candidate_id in ranked_candidates:
            if candidate_id != failed_provider_id:
                logger.warning(f"Initiating fallback: switching from failed provider '{failed_provider_id}' to '{candidate_id}'.")
                return candidate_id
        logger.error(f"No alternative fallback provider available after failure of '{failed_provider_id}'.")
        return None
