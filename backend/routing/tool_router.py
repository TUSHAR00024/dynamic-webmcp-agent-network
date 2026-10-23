"""Master Dynamic Tool Router: Coordinates discovery, ranking, translation, execution & fallback."""
import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple

from backend.adapters.base_adapter import BaseProviderAdapter
from backend.adapters.demo_provider_adapter import (
    ProviderAlphaAdapter,
    ProviderBetaAdapter,
    ProviderGammaAdapter
)
from backend.models.audit_event import RoutingDecisionRecord
from backend.models.product import ProductRecord
from backend.models.tool import ToolExecutionResult
from backend.registry.capability_map import CanonicalCapability
from backend.registry.provider_registry import provider_registry
from backend.registry.schema_normalizer import SchemaNormalizer
from backend.registry.tool_registry import tool_registry
from backend.routing.fallback_manager import FallbackManager
from backend.routing.parallel_executor import ParallelExecutor
from backend.routing.provider_ranker import provider_ranker
from backend.routing.routing_policy import RoutingPolicy

logger = logging.getLogger("Routing.ToolRouter")


class DynamicToolRouter:
    def __init__(self):
        # provider_id -> BaseProviderAdapter
        self._adapters: Dict[str, BaseProviderAdapter] = {}
        self._decision_history: List[RoutingDecisionRecord] = []
        self._initialize_default_adapters()

    def _initialize_default_adapters(self) -> None:
        """Register default demonstration adapters."""
        alpha = ProviderAlphaAdapter()
        beta = ProviderBetaAdapter()
        gamma = ProviderGammaAdapter(simulate_failure=True)

        self.register_adapter(alpha)
        self.register_adapter(beta)
        self.register_adapter(gamma)

    def register_adapter(self, adapter: BaseProviderAdapter) -> None:
        p_info = adapter.provider_info
        self._adapters[p_info.provider_id] = adapter

        # Register in global registries
        provider_registry.register_provider(p_info)
        for tool in adapter.discover_tools():
            tool_registry.register_tool(tool)

    def route_and_execute(
        self,
        canonical_capability: str,
        canonical_args: Dict[str, Any],
        preferred_provider_id: Optional[str] = None,
        task_id: Optional[str] = None,
        enable_fallback: bool = True
    ) -> Tuple[ToolExecutionResult, RoutingDecisionRecord]:
        """Dynamically route and execute a single capability with automatic fallback."""
        tid = task_id or f"task_{uuid.uuid4().hex[:8]}"

        # 1. Discover all candidate tools implementing this capability
        candidate_tools = tool_registry.find_tools_by_capability(canonical_capability, active_only=True)
        candidate_provider_ids = list({t.provider_id for t in candidate_tools})
        all_providers = [
            provider_registry.get_provider(pid)
            for pid in candidate_provider_ids
            if provider_registry.get_provider(pid) is not None
        ]

        # 2. Filter eligible providers via policy
        allow_degraded_eval = (preferred_provider_id is not None)
        eligible_providers, excluded = RoutingPolicy.filter_eligible_providers(
            all_providers,
            candidate_tools,
            canonical_capability,
            allow_degraded=allow_degraded_eval
        )

        if not eligible_providers and not allow_degraded_eval:
            # Check if degraded provider is available as secondary
            eligible_providers, excluded = RoutingPolicy.filter_eligible_providers(
                all_providers,
                candidate_tools,
                canonical_capability,
                allow_degraded=True
            )

        if not eligible_providers:
            fail_decision = RoutingDecisionRecord(
                decision_id=f"dec_{uuid.uuid4().hex[:8]}",
                task_id=tid,
                required_capability=canonical_capability,
                considered_providers=candidate_provider_ids,
                excluded_providers=excluded,
                scores={},
                selected_provider_id="NONE",
                selected_tool_name="NONE",
                rationale="No eligible providers could fulfill the requested capability.",
                execution_mode="NONE"
            )
            self._decision_history.append(fail_decision)
            err_res = ToolExecutionResult(
                action_id=f"act_err_{uuid.uuid4().hex[:8]}",
                tool_id="none",
                provider_id="none",
                tool_name=canonical_capability,
                status="FAILED",
                error_message=f"Capability '{canonical_capability}' has no eligible active providers."
            )
            return err_res, fail_decision

        # 3. Score and rank eligible providers
        score_breakdowns = provider_ranker.rank_providers(eligible_providers, canonical_capability)
        scores_map = {s.provider_id: s.composite_score for s in score_breakdowns}

        # 4. Select top provider (or respect preferred if eligible)
        selected_provider_id = score_breakdowns[0].provider_id
        if preferred_provider_id and any(p.provider_id == preferred_provider_id for p in eligible_providers):
            selected_provider_id = preferred_provider_id

        # 5. Retrieve provider tool and adapter
        tool_def = tool_registry.find_tool_for_provider(selected_provider_id, canonical_capability)
        adapter = self._adapters.get(selected_provider_id)

        if not tool_def or not adapter:
            raise RuntimeError(f"Adapter or tool definition missing for provider '{selected_provider_id}'.")

        # 6. Translate canonical request to provider's schema
        provider_args = SchemaNormalizer.translate_request_to_provider(
            canonical_capability,
            selected_provider_id,
            canonical_args
        )

        rationale = (
            f"Selected provider '{selected_provider_id}' (Tool: '{tool_def.tool_name}') with composite score "
            f"{scores_map.get(selected_provider_id, 0.0):.4f} for capability '{canonical_capability}'."
        )

        decision = RoutingDecisionRecord(
            decision_id=f"dec_{uuid.uuid4().hex[:8]}",
            task_id=tid,
            required_capability=canonical_capability,
            considered_providers=candidate_provider_ids,
            excluded_providers=excluded,
            scores=scores_map,
            selected_provider_id=selected_provider_id,
            selected_tool_name=tool_def.tool_name,
            rationale=rationale,
            execution_mode=tool_def.execution_mode.value
        )
        self._decision_history.append(decision)

        # 7. Execute tool on adapter
        logger.info(f"Executing '{tool_def.tool_name}' on provider '{selected_provider_id}' with args {provider_args}")
        exec_result = adapter.execute_tool(tool_def.tool_name, provider_args)

        # 8. Check for failure & trigger automatic fallback if enabled
        if FallbackManager.should_trigger_fallback(exec_result) and enable_fallback:
            ranked_ids = [s.provider_id for s in score_breakdowns]
            fallback_id = FallbackManager.select_fallback_provider(selected_provider_id, ranked_ids)

            if fallback_id and fallback_id in self._adapters:
                fb_tool = tool_registry.find_tool_for_provider(fallback_id, canonical_capability)
                fb_adapter = self._adapters[fallback_id]
                if fb_tool:
                    fb_args = SchemaNormalizer.translate_request_to_provider(
                        canonical_capability,
                        fallback_id,
                        canonical_args
                    )
                    logger.warning(f"Executing fallback tool '{fb_tool.tool_name}' on '{fallback_id}'.")
                    fb_result = fb_adapter.execute_tool(fb_tool.tool_name, fb_args)

                    decision.rationale += f" Primary provider failed ({exec_result.error_message}). Recovered via fallback provider '{fallback_id}'."
                    decision.selected_provider_id = fallback_id
                    decision.selected_tool_name = fb_tool.tool_name
                    return fb_result, decision

        return exec_result, decision

    def route_parallel_search(
        self,
        canonical_args: Dict[str, Any],
        task_id: Optional[str] = None
    ) -> Tuple[List[ProductRecord], List[RoutingDecisionRecord]]:
        """Search multiple eligible providers in parallel and merge normalized product records."""
        tid = task_id or f"task_{uuid.uuid4().hex[:8]}"
        candidate_tools = tool_registry.find_tools_by_capability(CanonicalCapability.PRODUCT_SEARCH, active_only=True)
        candidate_pids = list({t.provider_id for t in candidate_tools})

        all_providers = [
            provider_registry.get_provider(pid)
            for pid in candidate_pids
            if provider_registry.get_provider(pid) is not None
        ]
        eligible_providers, excluded = RoutingPolicy.filter_eligible_providers(
            all_providers,
            candidate_tools,
            CanonicalCapability.PRODUCT_SEARCH
        )

        decisions: List[RoutingDecisionRecord] = []
        parallel_tasks = []

        for p in eligible_providers:
            tool_def = tool_registry.find_tool_for_provider(p.provider_id, CanonicalCapability.PRODUCT_SEARCH)
            adapter = self._adapters.get(p.provider_id)
            if not tool_def or not adapter:
                continue

            provider_args = SchemaNormalizer.translate_request_to_provider(
                CanonicalCapability.PRODUCT_SEARCH,
                p.provider_id,
                canonical_args
            )

            decisions.append(RoutingDecisionRecord(
                decision_id=f"dec_{uuid.uuid4().hex[:8]}",
                task_id=tid,
                required_capability=CanonicalCapability.PRODUCT_SEARCH,
                considered_providers=candidate_pids,
                excluded_providers=excluded,
                scores={p.provider_id: p.historical_reliability},
                selected_provider_id=p.provider_id,
                selected_tool_name=tool_def.tool_name,
                rationale=f"Selected '{p.provider_id}' for parallel catalogue discovery.",
                execution_mode=tool_def.execution_mode.value
            ))

            def make_call(ad=adapter, tname=tool_def.tool_name, args=provider_args):
                return ad.execute_tool(tname, args)

            parallel_tasks.append((p.provider_id, make_call))

        # Execute parallel searches
        results_map = ParallelExecutor.execute_in_parallel(parallel_tasks, timeout_seconds=5.0)

        # Normalize and merge results
        merged_products: List[ProductRecord] = []
        seen_skus = set()

        for prov_id, res in results_map.items():
            if res.status != "SUCCESS":
                logger.warning(f"Parallel search for provider '{prov_id}' returned status {res.status}: {res.error_message}")
                continue

            raw_items = res.payload.get("products") or res.payload.get("items") or []
            for item in raw_items:
                normalized = SchemaNormalizer.normalize_product_record(prov_id, item)
                if normalized.sku not in seen_skus:
                    seen_skus.add(normalized.sku)
                    merged_products.append(normalized)

        return merged_products, decisions

    def get_decision_history(self) -> List[RoutingDecisionRecord]:
        return list(self._decision_history)


# Global tool router singleton
tool_router = DynamicToolRouter()
