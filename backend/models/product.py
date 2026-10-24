"""Canonical product and cart models for Dynamic WebMCP Agent Network."""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ProductSpecs:
    cpu: str = "unknown"
    ram: str = "unknown"
    storage: str = "unknown"
    display: str = "unknown"
    battery: str = "unknown"
    weight_kg: Optional[float] = None
    warranty: str = "unknown"
    os: str = "unknown"
    gpu: str = "unknown"
    category: str = "general"
    attributes: Dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        if hasattr(self, key):
            val = getattr(self, key)
            if val != "unknown" and val is not None:
                return val
        if self.attributes and key in self.attributes:
            return self.attributes[key]
        return getattr(self, key, default)

    def __getitem__(self, key: str) -> Any:
        val = self.get(key)
        if val is None:
            raise KeyError(key)
        return val

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # Flatten extra category-specific attributes into the top-level specs dict
        if self.attributes:
            for k, v in self.attributes.items():
                if k not in d:
                    d[k] = v
        return d

    def summary(self) -> str:
        """Produce dynamic, domain-aware human-readable summary of prominent specifications."""
        parts = []
        # Monitor features
        if self.get("refresh_rate") and self.get("refresh_rate") != "unknown":
            parts.append(str(self.get("refresh_rate")))
        if self.get("resolution") and self.get("resolution") != "unknown":
            parts.append(str(self.get("resolution")))
        if self.display != "unknown" and not any("inch" in p for p in parts):
            parts.append(self.display)

        # Furniture features
        if self.get("ergonomics") and self.get("ergonomics") != "unknown":
            parts.append(str(self.get("ergonomics")))
        if self.get("material") and self.get("material") != "unknown":
            parts.append(str(self.get("material")))

        # Cloud / Software features
        if self.get("tier") and self.get("tier") != "unknown":
            parts.append(str(self.get("tier")))
        if self.get("uptime_sla") and self.get("uptime_sla") != "unknown":
            parts.append(f"Uptime: {self.get('uptime_sla')}")
        if self.get("licenses") and self.get("licenses") != "unknown":
            parts.append(str(self.get("licenses")))

        # Laptop features
        if self.cpu != "unknown" and self.cpu not in parts:
            parts.append(self.cpu.split("(")[0].strip())
        if self.ram != "unknown" and self.ram not in parts:
            parts.append(self.ram)
        if self.battery != "unknown" and self.battery not in parts:
            parts.append(self.battery)

        # Warranty fallback if few parts
        if len(parts) < 2 and self.warranty != "unknown":
            parts.append(self.warranty)

        if not parts:
            return "Standard Specifications"
        return " • ".join(parts[:3])


@dataclass
class ProductRecord:
    product_id: str
    provider_id: str
    sku: str
    title: str
    brand: str
    price: float
    currency: str = "INR"
    category: str = "general"
    specs: ProductSpecs = field(default_factory=ProductSpecs)
    stock_status: str = "in_stock"
    stock_count: int = 10
    rating: float = 4.0
    reviews_count: int = 0
    product_url: str = ""
    image_url: str = ""
    provenance: str = "Demo Store Inventory"
    is_demo: bool = True
    verification_status: str = "verified"
    last_updated: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if isinstance(self.specs, ProductSpecs):
            d["specs"] = self.specs.to_dict()
        return d


@dataclass
class CartItemRecord:
    product_id: str
    provider_id: str
    sku: str
    title: str
    quantity: int
    unit_price: float
    total_price: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CartStateRecord:
    session_id: str
    provider_id: str
    cart_version: int
    items: List[CartItemRecord] = field(default_factory=list)
    subtotal: float = 0.0
    total: float = 0.0
    currency: str = "INR"
    last_verified: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "provider_id": self.provider_id,
            "cart_version": self.cart_version,
            "items": [i.to_dict() for i in self.items],
            "items_count": sum(i.quantity for i in self.items),
            "subtotal": self.subtotal,
            "total": self.total,
            "currency": self.currency,
            "last_verified": self.last_verified
        }
