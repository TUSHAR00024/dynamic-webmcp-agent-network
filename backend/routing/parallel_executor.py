"""Parallel tool executor across multiple providers."""
import concurrent.futures
import logging
from typing import Any, Callable, Dict, List, Tuple
from backend.models.tool import ToolExecutionResult

logger = logging.getLogger("Routing.ParallelExecutor")


class ParallelExecutor:
    @staticmethod
    def execute_in_parallel(
        tasks: List[Tuple[str, Callable[[], ToolExecutionResult]]],
        timeout_seconds: float = 5.0
    ) -> Dict[str, ToolExecutionResult]:
        """Execute multiple provider calls in parallel and aggregate results."""
        results: Dict[str, ToolExecutionResult] = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(tasks) or 1) as executor:
            future_to_provider = {
                executor.submit(fn): provider_id
                for provider_id, fn in tasks
            }

            for future in concurrent.futures.as_completed(future_to_provider, timeout=timeout_seconds):
                prov_id = future_to_provider[future]
                try:
                    res = future.result()
                    results[prov_id] = res
                except Exception as e:
                    logger.error(f"Error in parallel execution for provider '{prov_id}': {e}")
                    results[prov_id] = ToolExecutionResult(
                        action_id="err_parallel",
                        tool_id="unknown",
                        provider_id=prov_id,
                        tool_name="parallel_call",
                        status="FAILED",
                        error_message=str(e)
                    )

        return results
