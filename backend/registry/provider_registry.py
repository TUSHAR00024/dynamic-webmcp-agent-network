"""Provider Registry and health tracking."""
import logging
import time
from typing import Dict, List, Optional
from backend.models.provider import ProviderHealth, ProviderInfo, ProviderType

logger = logging.getLogger("Registry.ProviderRegistry")


class ProviderRegistry:
    def __init__(self):
        self._providers: Dict[str, ProviderInfo] = {}

    def register_provider(self, provider: ProviderInfo) -> None:
        self._providers[provider.provider_id] = provider
        logger.info(f"Registered provider '{provider.name}' ({provider.provider_id}) type={provider.provider_type.value}")

    def get_provider(self, provider_id: str) -> Optional[ProviderInfo]:
        return self._providers.get(provider_id)

    def update_health(self, provider_id: str, health: ProviderHealth) -> None:
        if provider_id in self._providers:
            self._providers[provider_id].health = health
            logger.info(f"Provider '{provider_id}' health updated to {health.value}")

    def list_providers(self, healthy_only: bool = False) -> List[ProviderInfo]:
        if healthy_only:
            return [p for p in self._providers.values() if p.health == ProviderHealth.HEALTHY]
        return list(self._providers.values())

    def clear(self) -> None:
        self._providers.clear()


# Global provider registry singleton
provider_registry = ProviderRegistry()
