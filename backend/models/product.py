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

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ProductRecord:
    product_id: str
    provider_id: str
    sku: str
    title: str
    brand: str
    price: float
    currency: str = "INR"
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
