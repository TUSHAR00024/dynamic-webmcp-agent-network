"""Two-Way Schema Normalization Layer for Dynamic WebMCP Agent Network."""
from typing import Any, Dict, List, Optional
from backend.models.product import CartItemRecord, CartStateRecord, ProductRecord, ProductSpecs
from backend.registry.capability_map import CanonicalCapability


class SchemaNormalizer:
    """Translates between canonical request/response models and provider-specific schemas."""

    @classmethod
    def translate_request_to_provider(
        cls,
        canonical_capability: str,
        provider_id: str,
        canonical_args: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Convert canonical arguments into provider's accepted argument schema."""

        # -------------------------------------------------------------
        # PRODUCT_SEARCH
        # -------------------------------------------------------------
        if canonical_capability == CanonicalCapability.PRODUCT_SEARCH:
            query = canonical_args.get("query", "")
            max_price = canonical_args.get("max_price")

            if provider_id == "provider_alpha":
                # Provider Alpha: { query: string, max_price?: number }
                out: Dict[str, Any] = {"query": query}
                if max_price is not None:
                    out["max_price"] = float(max_price)
                return out

            elif provider_id == "provider_beta":
                # Provider Beta: { keywords: string, budget?: number }
                out = {"keywords": query}
                if max_price is not None:
                    out["budget"] = float(max_price)
                return out

            elif provider_id == "provider_gamma":
                # Provider Gamma: { filter_dict: { q: string, ceiling: number } }
                filters: Dict[str, Any] = {"q": query}
                if max_price is not None:
                    filters["ceiling"] = float(max_price)
                return {"filter_dict": filters}

            # Generic fallback
            return dict(canonical_args)

        # -------------------------------------------------------------
        # PRODUCT_DETAILS
        # -------------------------------------------------------------
        elif canonical_capability == CanonicalCapability.PRODUCT_DETAILS:
            product_id = canonical_args.get("product_id", "")

            if provider_id == "provider_alpha":
                return {"product_id": product_id}
            elif provider_id == "provider_beta":
                # Beta uses `item_sku`
                return {"item_sku": product_id}
            elif provider_id == "provider_gamma":
                return {"target_id": product_id}

            return dict(canonical_args)

        # -------------------------------------------------------------
        # CART_ADD
        # -------------------------------------------------------------
        elif canonical_capability == CanonicalCapability.CART_ADD:
            session_id = canonical_args.get("session_id", "default_session")
            product_id = canonical_args.get("product_id", "")
            quantity = int(canonical_args.get("quantity", 1))

            if provider_id == "provider_alpha":
                return {
                    "session_id": session_id,
                    "product_id": product_id,
                    "quantity": quantity
                }
            elif provider_id == "provider_beta":
                # Beta uses `item_sku` and `count`
                return {
                    "session_id": session_id,
                    "item_sku": product_id,
                    "count": quantity
                }
            elif provider_id == "provider_gamma":
                return {
                    "basket_id": session_id,
                    "item_id": product_id,
                    "units": quantity
                }

            return dict(canonical_args)

        # -------------------------------------------------------------
        # CART_READ
        # -------------------------------------------------------------
        elif canonical_capability == CanonicalCapability.CART_READ:
            session_id = canonical_args.get("session_id", "default_session")
            if provider_id == "provider_alpha" or provider_id == "provider_beta":
                return {"session_id": session_id}
            elif provider_id == "provider_gamma":
                return {"basket_id": session_id}
            return dict(canonical_args)

        return dict(canonical_args)

    @classmethod
    def normalize_product_record(cls, provider_id: str, raw: Dict[str, Any]) -> ProductRecord:
        """Convert provider-specific product dictionary into canonical ProductRecord dynamically preserving attributes."""
        category = raw.get("category", "general")

        if provider_id == "provider_alpha":
            # Alpha schema: { id, sku, name, brand, price, currency, specs: { cpu, ram, storage... }, stock_quantity }
            raw_specs = raw.get("specs", {})
            # Separate standard fields from category-specific dynamic attributes
            standard_keys = {"cpu", "ram", "storage", "display", "battery", "weight_kg", "warranty", "os", "gpu"}
            extra_attrs = {k: v for k, v in raw_specs.items() if k not in standard_keys}

            specs = ProductSpecs(
                cpu=raw_specs.get("cpu", "unknown"),
                ram=raw_specs.get("ram", "unknown"),
                storage=raw_specs.get("storage", "unknown"),
                display=raw_specs.get("display", "unknown"),
                battery=raw_specs.get("battery", "unknown"),
                weight_kg=raw_specs.get("weight_kg"),
                warranty=raw_specs.get("warranty", "unknown"),
                os=raw_specs.get("os", "unknown"),
                category=category,
                attributes=extra_attrs
            )
            return ProductRecord(
                product_id=str(raw["id"]),
                provider_id=provider_id,
                sku=str(raw.get("sku", raw["id"])),
                title=str(raw["name"]),
                brand=str(raw.get("brand", "Unknown")),
                price=float(raw["price"]),
                currency=str(raw.get("currency", "INR")),
                category=category,
                specs=specs,
                stock_status=str(raw.get("stock_status", "in_stock")),
                stock_count=int(raw.get("stock_quantity", 10)),
                rating=float(raw.get("rating", 4.0)),
                reviews_count=int(raw.get("reviews_count", 0)),
                product_url=str(raw.get("product_url", "")),
                image_url=str(raw.get("image_url", "")),
                provenance="Provider Alpha (TechMart)",
                is_demo=True,
                verification_status="verified"
            )

        elif provider_id == "provider_beta":
            # Beta schema: { item_sku, item_title, manufacturer, cost, curr, hardware: { processor, memory, drive, screen, runtime_hours, guarantee } }
            hw = raw.get("hardware", {})
            battery_str = f"{hw.get('runtime_hours', 'unknown')} hrs" if "runtime_hours" in hw and hw["runtime_hours"] is not None else "unknown"
            standard_beta_keys = {"processor", "memory", "drive", "screen", "runtime_hours", "mass_kg", "guarantee", "operating_system"}
            extra_attrs = {k: v for k, v in hw.items() if k not in standard_beta_keys}

            specs = ProductSpecs(
                cpu=hw.get("processor", "unknown"),
                ram=hw.get("memory", "unknown"),
                storage=hw.get("drive", "unknown"),
                display=hw.get("screen", "unknown"),
                battery=battery_str,
                weight_kg=hw.get("mass_kg"),
                warranty=hw.get("guarantee", "unknown"),
                os=hw.get("operating_system", "unknown"),
                category=category,
                attributes=extra_attrs
            )
            return ProductRecord(
                product_id=str(raw["item_sku"]),
                provider_id=provider_id,
                sku=str(raw["item_sku"]),
                title=str(raw["item_title"]),
                brand=str(raw.get("manufacturer", "Unknown")),
                price=float(raw["cost"]),
                currency=str(raw.get("curr", "INR")),
                category=category,
                specs=specs,
                stock_status="in_stock" if int(raw.get("units_available", 1)) > 0 else "out_of_stock",
                stock_count=int(raw.get("units_available", 5)),
                rating=float(raw.get("customer_rating", 4.2)),
                reviews_count=int(raw.get("total_reviews", 0)),
                product_url=f"/provider-beta/items/{raw['item_sku']}",
                image_url=str(raw.get("image", "")),
                provenance="Provider Beta (ElectroStore Pro)",
                is_demo=True,
                verification_status="verified"
            )

        # Fallback generic mapping
        raw_specs = raw.get("specs") or raw.get("attributes") or {}
        specs = ProductSpecs(category=category, attributes=dict(raw_specs)) if isinstance(raw_specs, dict) else ProductSpecs()
        return ProductRecord(
            product_id=str(raw.get("id") or raw.get("sku") or "unknown_id"),
            provider_id=provider_id,
            sku=str(raw.get("sku") or raw.get("id") or "unknown_sku"),
            title=str(raw.get("title") or raw.get("name") or "Unnamed Product"),
            brand=str(raw.get("brand") or "Generic"),
            price=float(raw.get("price") or raw.get("cost") or 0.0),
            currency=str(raw.get("currency") or "INR"),
            category=category,
            specs=specs,
            provenance=f"Provider {provider_id}",
            is_demo=True,
            verification_status="unverified"
        )

    @classmethod
    def normalize_cart_state(cls, provider_id: str, raw: Dict[str, Any]) -> CartStateRecord:
        """Convert provider-specific cart response to canonical CartStateRecord."""
        session_id = raw.get("session_id") or raw.get("basket_id") or "default_session"
        cart_version = int(raw.get("cart_version") or raw.get("version") or 1)
        subtotal = float(raw.get("subtotal") or raw.get("total") or raw.get("net_amount") or 0.0)

        items: List[CartItemRecord] = []
        raw_items = raw.get("items") or raw.get("lines") or []
        for ri in raw_items:
            pid = str(ri.get("product_id") or ri.get("item_sku") or ri.get("id"))
            sku = str(ri.get("sku") or pid)
            title = str(ri.get("name") or ri.get("title") or pid)
            qty = int(ri.get("quantity") or ri.get("count") or ri.get("units") or 1)
            unit_price = float(ri.get("unit_price") or ri.get("cost") or 0.0)
            items.append(CartItemRecord(
                product_id=pid,
                provider_id=provider_id,
                sku=sku,
                title=title,
                quantity=qty,
                unit_price=unit_price,
                total_price=qty * unit_price
            ))

        return CartStateRecord(
            session_id=session_id,
            provider_id=provider_id,
            cart_version=cart_version,
            items=items,
            subtotal=subtotal,
            total=subtotal,
            currency="INR"
        )
