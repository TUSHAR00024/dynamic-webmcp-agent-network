"""Concrete adapters for demonstration providers (Alpha, Beta, Gamma)."""
import re
import time
import uuid
from typing import Any, Dict, List, Optional
from backend.adapters.base_adapter import BaseProviderAdapter
from backend.models.provider import ProviderHealth, ProviderInfo, ProviderType
from backend.models.tool import ExecutionMode, ToolClassification, ToolDefinition, ToolExecutionResult, ToolStatus
from backend.registry.capability_map import CanonicalCapability


class ProviderAlphaAdapter(BaseProviderAdapter):
    """Provider Alpha (TechMart Online) - WebMCP E-Commerce Website.

    Exposes:
    - search_products(query: str, max_price?: float) -> { products: list, count: int }
    - get_product_details(product_id: str) -> { product: dict }
    - add_to_cart(session_id: str, product_id: str, quantity: int) -> { session_id, product_id, quantity, cart_version }
    - get_cart(session_id: str) -> { session_id, cart_version, items: list, subtotal: float }
    """

    def __init__(self):
        self._provider_info = ProviderInfo(
            provider_id="provider_alpha",
            name="TechMart Online",
            description="Leading authorized technology retailer with enterprise laptop lines.",
            provider_type=ProviderType.WEBMCP_SITE,
            origin_url="https://techmart.example.com",
            supported_capabilities=[
                CanonicalCapability.PRODUCT_SEARCH,
                CanonicalCapability.PRODUCT_DETAILS,
                CanonicalCapability.CART_ADD,
                CanonicalCapability.CART_READ
            ],
            health=ProviderHealth.HEALTHY,
            data_quality_score=0.96,
            historical_reliability=0.98,
            average_latency_ms=85.0
        )

        # Realistic inventory
        self._products = {
            "alpha_thinkpad_e14": {
                "id": "alpha_thinkpad_e14",
                "sku": "LNV-TP-E14-G5",
                "name": "Lenovo ThinkPad E14 Gen 5 Laptop",
                "brand": "Lenovo",
                "category": "laptops",
                "price": 64990.0,
                "currency": "INR",
                "specs": {
                    "cpu": "AMD Ryzen 7 7730U (8 cores, 16 threads, up to 4.5 GHz)",
                    "ram": "16GB DDR4 3200MHz",
                    "storage": "512GB NVMe M.2 SSD",
                    "display": "14.0-inch WUXGA (1920 x 1200) IPS Anti-glare 300 nits",
                    "battery": "57Wh (estimated 9.5 hours productivity)",
                    "weight_kg": 1.41,
                    "warranty": "3-Year Premier Support Onsite",
                    "os": "Windows 11 Home"
                },
                "stock_quantity": 14,
                "rating": 4.6,
                "reviews_count": 182,
                "product_url": "https://techmart.example.com/p/alpha_thinkpad_e14"
            },
            "alpha_swift_go14": {
                "id": "alpha_swift_go14",
                "sku": "ACR-SW-GO14-I5",
                "name": "Acer Swift Go 14 Laptop",
                "brand": "Acer",
                "category": "laptops",
                "price": 58990.0,
                "currency": "INR",
                "specs": {
                    "cpu": "Intel Core i5-1335U (10 cores, 12 threads)",
                    "ram": "16GB LPDDR5 4800MHz",
                    "storage": "512GB PCIe Gen4 SSD",
                    "display": "14.0-inch WUXGA (1920 x 1200) IPS 100% sRGB",
                    "battery": "65Wh (estimated 8.5 hours)",
                    "weight_kg": 1.25,
                    "warranty": "1-Year International Travelers Warranty",
                    "os": "Windows 11 Home"
                },
                "stock_quantity": 11,
                "rating": 4.4,
                "reviews_count": 67,
                "product_url": "https://techmart.example.com/p/alpha_swift_go14"
            },
            "alpha_inspiron_15": {
                "id": "alpha_inspiron_15",
                "sku": "DLL-INS-3520-U",
                "name": "Dell Inspiron 15 3520 Laptop",
                "brand": "Dell",
                "category": "laptops",
                "price": 47990.0,
                "currency": "INR",
                "specs": {
                    "cpu": "Intel Core i5-1235U (10 cores, 12 threads)",
                    "ram": "8GB DDR4 2666MHz",
                    "storage": "512GB NVMe M.2 SSD",
                    "display": "15.6-inch FHD (1920 x 1080) 120Hz",
                    "battery": "unknown",  # Missing info test
                    "weight_kg": 1.65,
                    "warranty": "1-Year Hardware Service with Onsite",
                    "os": "Windows 11 Home"
                },
                "stock_quantity": 19,
                "rating": 4.1,
                "reviews_count": 142,
                "product_url": "https://techmart.example.com/p/alpha_inspiron_15"
            },
            "alpha_macbook_air_m2": {
                "id": "alpha_macbook_air_m2",
                "sku": "APL-MBA-M2-256",
                "name": "Apple MacBook Air 13-inch (M2)",
                "brand": "Apple",
                "category": "laptops",
                "price": 89900.0,  # Over-budget limit test
                "currency": "INR",
                "specs": {
                    "cpu": "Apple M2 Chip (8-core CPU, 8-core GPU)",
                    "ram": "8GB Unified Memory",
                    "storage": "256GB SSD",
                    "display": "13.6-inch Liquid Retina True Tone",
                    "battery": "52.6Wh (estimated 15 hours)",
                    "weight_kg": 1.24,
                    "warranty": "1-Year Limited Warranty",
                    "os": "macOS Sonoma"
                },
                "stock_quantity": 12,
                "rating": 4.8,
                "reviews_count": 520,
                "product_url": "https://techmart.example.com/p/alpha_macbook_air_m2"
            },
            # --- Open-Domain Additions: Monitors, Furniture, Cloud Services ---
            "alpha_dell_u2723qe": {
                "id": "alpha_dell_u2723qe",
                "sku": "DLL-MN-U2723QE-4K",
                "name": "Dell UltraSharp U2723QE 27-inch 4K UHD Monitor",
                "brand": "Dell",
                "category": "monitors",
                "price": 54990.0,
                "currency": "INR",
                "specs": {
                    "display": "27.0-inch 4K UHD (3840 x 2160) IPS Black",
                    "refresh_rate": "60Hz",
                    "resolution": "4K UHD 2160p",
                    "ports": "USB-C 90W PD, HDMI, DisplayPort 1.4, RJ45",
                    "warranty": "3-Year Advanced Exchange Service",
                    "color_gamut": "100% sRGB, 98% DCI-P3"
                },
                "stock_quantity": 18,
                "rating": 4.8,
                "reviews_count": 215,
                "product_url": "https://techmart.example.com/p/alpha_dell_u2723qe"
            },
            "alpha_lg_27gr75q": {
                "id": "alpha_lg_27gr75q",
                "sku": "LG-MN-27GR75Q-QHD",
                "name": "LG UltraGear 27GR75Q 27-inch QHD Gaming Monitor",
                "brand": "LG",
                "category": "monitors",
                "price": 24990.0,
                "currency": "INR",
                "specs": {
                    "display": "27.0-inch QHD (2560 x 1440) IPS 1ms G-Sync",
                    "refresh_rate": "165Hz",
                    "resolution": "QHD 1440p",
                    "ports": "2x HDMI 2.0, DisplayPort 1.4",
                    "warranty": "3-Year Onsite Warranty",
                    "hdr": "HDR10"
                },
                "stock_quantity": 25,
                "rating": 4.6,
                "reviews_count": 340,
                "product_url": "https://techmart.example.com/p/alpha_lg_27gr75q"
            },
            "alpha_featherlite_helix": {
                "id": "alpha_featherlite_helix",
                "sku": "FTH-CH-HELIX-HB",
                "name": "Featherlite Helix High-Back Ergonomic Office Chair",
                "brand": "Featherlite",
                "category": "furniture",
                "price": 18990.0,
                "currency": "INR",
                "specs": {
                    "material": "Breathable Korean Mesh & Aluminum Alloy",
                    "ergonomics": "Adjustable Lumbar Support, 3D Armrests, Multi-lock Synchro Tilt",
                    "weight_capacity": "135 kg",
                    "warranty": "3-Year Manufacturer Warranty"
                },
                "stock_quantity": 15,
                "rating": 4.5,
                "reviews_count": 89,
                "product_url": "https://techmart.example.com/p/alpha_featherlite_helix"
            },
            "alpha_aws_cloud_tier": {
                "id": "alpha_aws_cloud_tier",
                "sku": "AWS-CL-COMPUTE-PRO",
                "name": "AWS Cloud Compute Enterprise Tier Credits",
                "brand": "AWS",
                "category": "cloud_services",
                "price": 34990.0,
                "currency": "INR",
                "specs": {
                    "tier": "Enterprise Cloud Compute Tier",
                    "vcpus": "32 vCPUs Allocated",
                    "ram": "128GB Cloud Memory Pool",
                    "uptime_sla": "99.99%",
                    "support": "24/7 Enterprise Dedicated Support",
                    "warranty": "Enterprise Cloud SLA"
                },
                "stock_quantity": 999,
                "rating": 4.9,
                "reviews_count": 412,
                "product_url": "https://techmart.example.com/p/alpha_aws_cloud_tier"
            }
        }

        # Stateful in-memory carts: session_id -> { "cart_version": int, "items": { product_id: qty } }
        self._carts: Dict[str, Dict[str, Any]] = {}

    @property
    def provider_info(self) -> ProviderInfo:
        return self._provider_info

    def discover_tools(self) -> List[ToolDefinition]:
        return [
            ToolDefinition(
                tool_id="alpha_tool_search",
                provider_id="provider_alpha",
                tool_name="search_products",
                description="Search TechMart catalog for laptops by keyword query and optional max budget.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search keyword query"},
                        "max_price": {"type": "number", "description": "Maximum ceiling price"}
                    },
                    "required": ["query"]
                },
                canonical_capability=CanonicalCapability.PRODUCT_SEARCH,
                classification=ToolClassification.READ_ONLY,
                requires_user_approval=False,
                execution_mode=ExecutionMode.WEBMCP_BROWSER
            ),
            ToolDefinition(
                tool_id="alpha_tool_details",
                provider_id="provider_alpha",
                tool_name="get_product_details",
                description="Retrieve full hardware specifications and real-time inventory from TechMart.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "product_id": {"type": "string", "description": "Product ID or SKU"}
                    },
                    "required": ["product_id"]
                },
                canonical_capability=CanonicalCapability.PRODUCT_DETAILS,
                classification=ToolClassification.READ_ONLY,
                requires_user_approval=False,
                execution_mode=ExecutionMode.WEBMCP_BROWSER
            ),
            ToolDefinition(
                tool_id="alpha_tool_cart_add",
                provider_id="provider_alpha",
                tool_name="add_to_cart",
                description="Add specified product ID to user shopping cart in TechMart.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string"},
                        "product_id": {"type": "string"},
                        "quantity": {"type": "integer"}
                    },
                    "required": ["session_id", "product_id", "quantity"]
                },
                canonical_capability=CanonicalCapability.CART_ADD,
                classification=ToolClassification.REVERSIBLE_STATE_CHANGE,
                requires_user_approval=True,
                execution_mode=ExecutionMode.WEBMCP_BROWSER
            ),
            ToolDefinition(
                tool_id="alpha_tool_get_cart",
                provider_id="provider_alpha",
                tool_name="get_cart",
                description="Inspect active shopping cart items and calculated subtotal on TechMart.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string"}
                    },
                    "required": ["session_id"]
                },
                canonical_capability=CanonicalCapability.CART_READ,
                classification=ToolClassification.READ_ONLY,
                requires_user_approval=False,
                execution_mode=ExecutionMode.WEBMCP_BROWSER
            )
        ]

    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> ToolExecutionResult:
        start_t = time.time()
        action_id = f"act_alpha_{uuid.uuid4().hex[:8]}"

        if tool_name == "search_products":
            q = str(arguments.get("query", "")).lower().strip()
            max_p = arguments.get("max_price")
            matches = []
            q_terms = [t for t in re.split(r"[\s,]+", q) if len(t) > 2]

            for p in self._products.values():
                if max_p is not None and p["price"] > float(max_p):
                    continue
                cat = p.get("category", "")
                specs_dict = p.get("specs", {})
                specs_str = " ".join(f"{k} {v}" for k, v in specs_dict.items())
                searchable = f"{p['name']} {p['brand']} {cat} {specs_str}".lower()

                if not q:
                    matches.append(p)
                elif q in searchable:
                    matches.append(p)
                elif q_terms and any(t in searchable for t in q_terms):
                    matches.append(p)
                elif "laptop" in q and ("laptop" in searchable or cat == "laptops"):
                    matches.append(p)

            dur = (time.time() - start_t) * 1000
            return ToolExecutionResult(
                action_id=action_id,
                tool_id="alpha_tool_search",
                provider_id="provider_alpha",
                tool_name=tool_name,
                status="SUCCESS",
                payload={"products": matches, "count": len(matches)},
                verified_postcondition=True,
                verification_details=f"Discovered {len(matches)} matching products from TechMart.",
                execution_time_ms=round(dur, 2)
            )

        elif tool_name == "get_product_details":
            pid = arguments.get("product_id")
            if pid in self._products:
                dur = (time.time() - start_t) * 1000
                return ToolExecutionResult(
                    action_id=action_id,
                    tool_id="alpha_tool_details",
                    provider_id="provider_alpha",
                    tool_name=tool_name,
                    status="SUCCESS",
                    payload={"product": self._products[pid]},
                    verified_postcondition=True,
                    verification_details="Product details retrieved from authoritative TechMart inventory.",
                    execution_time_ms=round(dur, 2)
                )
            dur = (time.time() - start_t) * 1000
            return ToolExecutionResult(
                action_id=action_id,
                tool_id="alpha_tool_details",
                provider_id="provider_alpha",
                tool_name=tool_name,
                status="FAILED",
                error_message=f"Product '{pid}' not found on TechMart.",
                execution_time_ms=round(dur, 2)
            )

        elif tool_name == "add_to_cart":
            sess_id = arguments.get("session_id", "default_session")
            pid = arguments.get("product_id")
            qty = int(arguments.get("quantity", 1))

            if pid not in self._products:
                dur = (time.time() - start_t) * 1000
                return ToolExecutionResult(
                    action_id=action_id,
                    tool_id="alpha_tool_cart_add",
                    provider_id="provider_alpha",
                    tool_name=tool_name,
                    status="FAILED",
                    error_message=f"Product '{pid}' does not exist.",
                    execution_time_ms=round(dur, 2)
                )

            if sess_id not in self._carts:
                self._carts[sess_id] = {"cart_version": 1, "items": {}}

            cart = self._carts[sess_id]
            cart["items"][pid] = cart["items"].get(pid, 0) + qty
            cart["cart_version"] += 1

            dur = (time.time() - start_t) * 1000
            return ToolExecutionResult(
                action_id=action_id,
                tool_id="alpha_tool_cart_add",
                provider_id="provider_alpha",
                tool_name=tool_name,
                status="VERIFIED",
                payload={
                    "session_id": sess_id,
                    "product_id": pid,
                    "quantity": qty,
                    "cart_version": cart["cart_version"]
                },
                verified_postcondition=True,
                verification_details=f"Added {qty}x of {pid} to TechMart cart session '{sess_id}'.",
                execution_time_ms=round(dur, 2)
            )

        elif tool_name == "get_cart":
            sess_id = arguments.get("session_id", "default_session")
            cart = self._carts.get(sess_id, {"cart_version": 1, "items": {}})
            items = []
            subtotal = 0.0
            for pid, qty in cart["items"].items():
                p = self._products.get(pid, {})
                unit_price = p.get("price", 0.0)
                subtotal += qty * unit_price
                items.append({
                    "product_id": pid,
                    "sku": p.get("sku", pid),
                    "name": p.get("name", pid),
                    "quantity": qty,
                    "unit_price": unit_price
                })

            dur = (time.time() - start_t) * 1000
            return ToolExecutionResult(
                action_id=action_id,
                tool_id="alpha_tool_get_cart",
                provider_id="provider_alpha",
                tool_name=tool_name,
                status="SUCCESS",
                payload={
                    "session_id": sess_id,
                    "cart_version": cart["cart_version"],
                    "items": items,
                    "subtotal": subtotal
                },
                verified_postcondition=True,
                verification_details=f"Verified TechMart cart state: {len(items)} items, subtotal ₹{subtotal:,.2f}.",
                execution_time_ms=round(dur, 2)
            )

        dur = (time.time() - start_t) * 1000
        return ToolExecutionResult(
            action_id=action_id,
            tool_id="unknown",
            provider_id="provider_alpha",
            tool_name=tool_name,
            status="FAILED",
            error_message=f"Tool '{tool_name}' unsupported on TechMart.",
            execution_time_ms=round(dur, 2)
        )

    def get_health(self) -> ProviderHealth:
        return self._provider_info.health


class ProviderBetaAdapter(BaseProviderAdapter):
    """Provider Beta (ElectroStore Pro) - Remote MCP Tool Server.

    Completely divergent tool names and schemas!
    - find_items(keywords: str, budget?: float) -> { items: list, total_found: int }
    - fetch_specs(item_sku: str) -> { item: dict }
    - cart_add(session_id: str, item_sku: str, count: int) -> { session_id, item_sku, count, version }
    - view_basket(session_id: str) -> { session_id, version, lines: list, net_amount: float }
    """

    def __init__(self):
        self._provider_info = ProviderInfo(
            provider_id="provider_beta",
            name="ElectroStore Pro",
            description="Consumer electronics distributor with aggressive discounts and gaming gear.",
            provider_type=ProviderType.REMOTE_MCP,
            origin_url="https://mcp.electrostore.example.com",
            supported_capabilities=[
                CanonicalCapability.PRODUCT_SEARCH,
                CanonicalCapability.PRODUCT_DETAILS,
                CanonicalCapability.CART_ADD,
                CanonicalCapability.CART_READ
            ],
            health=ProviderHealth.HEALTHY,
            data_quality_score=0.92,
            historical_reliability=0.96,
            average_latency_ms=110.0
        )

        # Inventory using Beta's internal field names
        self._items = {
            "beta_vivobook_s14": {
                "item_sku": "beta_vivobook_s14",
                "item_title": "ASUS Vivobook S 14 OLED Laptop",
                "manufacturer": "ASUS",
                "category": "laptops",
                "cost": 68990.0,
                "curr": "INR",
                "hardware": {
                    "processor": "Intel Core i5-13500H (12 cores, 16 threads, up to 4.7 GHz)",
                    "memory": "16GB LPDDR5 4800MHz",
                    "drive": "512GB PCIe 4.0 NVMe SSD",
                    "screen": "14.0-inch 2.8K 90Hz OLED 600 nits HDR",
                    "runtime_hours": 10.5,
                    "mass_kg": 1.50,
                    "guarantee": "1-Year Manufacturer Warranty",
                    "operating_system": "Windows 11 Home"
                },
                "units_available": 8,
                "customer_rating": 4.7,
                "total_reviews": 94
            },
            "beta_latitude_3440": {
                "item_sku": "beta_latitude_3440",
                "item_title": "Dell Latitude 3440 Enterprise Laptop",
                "manufacturer": "Dell",
                "category": "laptops",
                "cost": 62490.0,
                "curr": "INR",
                "hardware": {
                    "processor": "Intel Core i5-1335U (10 cores, 12 threads)",
                    "memory": "16GB DDR4 3200MHz",
                    "drive": "512GB PCIe NVMe SSD",
                    "screen": "14.0-inch FHD (1920 x 1080) Anti-glare",
                    "runtime_hours": 7.5,
                    "mass_kg": 1.54,
                    "guarantee": "unknown",  # Missing warranty test
                    "operating_system": "Windows 11 Pro"
                },
                "units_available": 5,
                "customer_rating": 4.3,
                "total_reviews": 39
            },
            "beta_tuf_f15": {
                "item_sku": "beta_tuf_f15",
                "item_title": "ASUS TUF Gaming F15 Laptop",
                "manufacturer": "ASUS",
                "category": "laptops",
                "cost": 54990.0,
                "curr": "INR",
                "hardware": {
                    "processor": "Intel Core i5-11400H (6 cores, 12 threads)",
                    "memory": "16GB DDR4 3200MHz",
                    "drive": "512GB PCIe 3.0 NVMe SSD",
                    "screen": "15.6-inch FHD 144Hz IPS",
                    "runtime_hours": 3.5,  # Low battery test
                    "mass_kg": 2.30,
                    "guarantee": "1-Year Warranty",
                    "operating_system": "Windows 11 Home"
                },
                "units_available": 9,
                "customer_rating": 4.4,
                "total_reviews": 310
            },
            "beta_hp_pavilion_14": {
                "item_sku": "beta_hp_pavilion_14",
                "item_title": "HP Pavilion 14 x360",
                "manufacturer": "HP",
                "category": "laptops",
                "cost": 74990.0,  # Over-budget limit test
                "curr": "INR",
                "hardware": {
                    "processor": "Intel Core i7-1355U",
                    "memory": "16GB DDR4",
                    "drive": "1TB SSD",
                    "screen": "14.0-inch Touch",
                    "runtime_hours": 6.0,
                    "guarantee": "1-Year Onsite"
                },
                "units_available": 6,
                "customer_rating": 4.5,
                "total_reviews": 88
            },
            # --- Open-Domain Additions: Monitors, Furniture, Subscriptions ---
            "beta_samsung_odyssey_g5": {
                "item_sku": "beta_samsung_odyssey_g5",
                "item_title": "Samsung Odyssey G5 32-inch Curved QHD Gaming Monitor",
                "manufacturer": "Samsung",
                "category": "monitors",
                "cost": 26990.0,
                "curr": "INR",
                "hardware": {
                    "screen": "32.0-inch 1000R Curved QHD (2560x1440) 165Hz 1ms",
                    "refresh_rate": "165Hz",
                    "resolution": "QHD 1440p",
                    "response_time": "1ms MPRT",
                    "guarantee": "3-Year Manufacturer Warranty"
                },
                "units_available": 14,
                "customer_rating": 4.6,
                "total_reviews": 182
            },
            "beta_benq_pd2705u": {
                "item_sku": "beta_benq_pd2705u",
                "item_title": "BenQ DesignVue PD2705U 27-inch 4K Designer Monitor",
                "manufacturer": "BenQ",
                "category": "monitors",
                "cost": 46990.0,
                "curr": "INR",
                "hardware": {
                    "screen": "27.0-inch 4K UHD (3840x2160) IPS 100% sRGB / Rec.709",
                    "refresh_rate": "60Hz",
                    "resolution": "4K UHD 2160p",
                    "ports": "USB-C 65W PD, HDMI 2.0, DisplayPort 1.4",
                    "guarantee": "3-Year Onsite Warranty"
                },
                "units_available": 7,
                "customer_rating": 4.7,
                "total_reviews": 75
            },
            "beta_steelcase_series1": {
                "item_sku": "beta_steelcase_series1",
                "item_title": "Steelcase Series 1 Ergonomic Task Chair",
                "manufacturer": "Steelcase",
                "category": "furniture",
                "cost": 38990.0,
                "curr": "INR",
                "hardware": {
                    "frame": "LiveBack Flexor Technology, 4D Adjustable Arms",
                    "ergonomics": "Weight-Activated Synchro-Tilt, Height-Adjustable Lumbar",
                    "guarantee": "12-Year Multi-Shift Warranty"
                },
                "units_available": 10,
                "customer_rating": 4.8,
                "total_reviews": 110
            },
            "beta_jetbrains_all_pack": {
                "item_sku": "beta_jetbrains_all_pack",
                "item_title": "JetBrains All Products Pack Commercial Subscription",
                "manufacturer": "JetBrains",
                "category": "software_subscriptions",
                "cost": 49900.0,
                "curr": "INR",
                "hardware": {
                    "licenses": "Complete 16 IDEs Commercial License (IntelliJ, PyCharm, WebStorm, GoLand)",
                    "tier": "Annual Commercial Cloud Subscription",
                    "platform": "Cross-Platform Cloud-Synced",
                    "guarantee": "1-Year Full Commercial Updates & Fallback Perpetual"
                },
                "units_available": 999,
                "customer_rating": 4.9,
                "total_reviews": 512
            }
        }

        self._baskets: Dict[str, Dict[str, Any]] = {}

    @property
    def provider_info(self) -> ProviderInfo:
        return self._provider_info

    def discover_tools(self) -> List[ToolDefinition]:
        return [
            ToolDefinition(
                tool_id="beta_tool_find",
                provider_id="provider_beta",
                tool_name="find_items",
                description="Query ElectroStore Pro MCP server for matching electronics with price ceiling.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "keywords": {"type": "string"},
                        "budget": {"type": "number"}
                    },
                    "required": ["keywords"]
                },
                canonical_capability=CanonicalCapability.PRODUCT_SEARCH,
                classification=ToolClassification.READ_ONLY,
                requires_user_approval=False,
                execution_mode=ExecutionMode.REMOTE_MCP
            ),
            ToolDefinition(
                tool_id="beta_tool_specs",
                provider_id="provider_beta",
                tool_name="fetch_specs",
                description="Fetch raw hardware spec sheet and warranty from ElectroStore Pro.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "item_sku": {"type": "string"}
                    },
                    "required": ["item_sku"]
                },
                canonical_capability=CanonicalCapability.PRODUCT_DETAILS,
                classification=ToolClassification.READ_ONLY,
                requires_user_approval=False,
                execution_mode=ExecutionMode.REMOTE_MCP
            ),
            ToolDefinition(
                tool_id="beta_tool_cart_add",
                provider_id="provider_beta",
                tool_name="cart_add",
                description="Append item count to ElectroStore user basket.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string"},
                        "item_sku": {"type": "string"},
                        "count": {"type": "integer"}
                    },
                    "required": ["session_id", "item_sku", "count"]
                },
                canonical_capability=CanonicalCapability.CART_ADD,
                classification=ToolClassification.REVERSIBLE_STATE_CHANGE,
                requires_user_approval=True,
                execution_mode=ExecutionMode.REMOTE_MCP
            ),
            ToolDefinition(
                tool_id="beta_tool_view_basket",
                provider_id="provider_beta",
                tool_name="view_basket",
                description="Fetch current basket lines and total from ElectroStore Pro.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string"}
                    },
                    "required": ["session_id"]
                },
                canonical_capability=CanonicalCapability.CART_READ,
                classification=ToolClassification.READ_ONLY,
                requires_user_approval=False,
                execution_mode=ExecutionMode.REMOTE_MCP
            )
        ]

    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> ToolExecutionResult:
        start_t = time.time()
        action_id = f"act_beta_{uuid.uuid4().hex[:8]}"

        if tool_name == "find_items":
            kw = str(arguments.get("keywords", "")).lower().strip()
            budget = arguments.get("budget")
            matches = []
            kw_terms = [t for t in re.split(r"[\s,]+", kw) if len(t) > 2]

            for item in self._items.values():
                if budget is not None and item["cost"] > float(budget):
                    continue
                cat = item.get("category", "")
                hw_dict = item.get("hardware", {})
                hw_str = " ".join(f"{k} {v}" for k, v in hw_dict.items())
                searchable = f"{item['item_title']} {item['manufacturer']} {cat} {hw_str}".lower()

                if not kw:
                    matches.append(item)
                elif kw in searchable:
                    matches.append(item)
                elif kw_terms and any(t in searchable for t in kw_terms):
                    matches.append(item)
                elif "laptop" in kw and ("laptop" in searchable or cat == "laptops"):
                    matches.append(item)

            dur = (time.time() - start_t) * 1000
            return ToolExecutionResult(
                action_id=action_id,
                tool_id="beta_tool_find",
                provider_id="provider_beta",
                tool_name=tool_name,
                status="SUCCESS",
                payload={"items": matches, "total_found": len(matches)},
                verified_postcondition=True,
                verification_details=f"Discovered {len(matches)} items from ElectroStore Pro.",
                execution_time_ms=round(dur, 2)
            )

        elif tool_name == "fetch_specs":
            sku = arguments.get("item_sku")
            if sku in self._items:
                dur = (time.time() - start_t) * 1000
                return ToolExecutionResult(
                    action_id=action_id,
                    tool_id="beta_tool_specs",
                    provider_id="provider_beta",
                    tool_name=tool_name,
                    status="SUCCESS",
                    payload={"item": self._items[sku]},
                    verified_postcondition=True,
                    verification_details="Item specs fetched from ElectroStore Pro.",
                    execution_time_ms=round(dur, 2)
                )
            dur = (time.time() - start_t) * 1000
            return ToolExecutionResult(
                action_id=action_id,
                tool_id="beta_tool_specs",
                provider_id="provider_beta",
                tool_name=tool_name,
                status="FAILED",
                error_message=f"Item SKU '{sku}' not found on ElectroStore Pro.",
                execution_time_ms=round(dur, 2)
            )

        elif tool_name == "cart_add":
            sess_id = arguments.get("session_id", "default_session")
            sku = arguments.get("item_sku")
            count = int(arguments.get("count", 1))

            if sku not in self._items:
                dur = (time.time() - start_t) * 1000
                return ToolExecutionResult(
                    action_id=action_id,
                    tool_id="beta_tool_cart_add",
                    provider_id="provider_beta",
                    tool_name=tool_name,
                    status="FAILED",
                    error_message=f"Item SKU '{sku}' does not exist.",
                    execution_time_ms=round(dur, 2)
                )

            if sess_id not in self._baskets:
                self._baskets[sess_id] = {"version": 1, "lines": {}}

            basket = self._baskets[sess_id]
            basket["lines"][sku] = basket["lines"].get(sku, 0) + count
            basket["version"] += 1

            dur = (time.time() - start_t) * 1000
            return ToolExecutionResult(
                action_id=action_id,
                tool_id="beta_tool_cart_add",
                provider_id="provider_beta",
                tool_name=tool_name,
                status="VERIFIED",
                payload={
                    "session_id": sess_id,
                    "item_sku": sku,
                    "count": count,
                    "version": basket["version"]
                },
                verified_postcondition=True,
                verification_details=f"Committed {count}x of {sku} to ElectroStore basket '{sess_id}'.",
                execution_time_ms=round(dur, 2)
            )

        elif tool_name == "view_basket":
            sess_id = arguments.get("session_id", "default_session")
            basket = self._baskets.get(sess_id, {"version": 1, "lines": {}})
            lines = []
            net_amount = 0.0
            for sku, count in basket["lines"].items():
                item = self._items.get(sku, {})
                unit_cost = item.get("cost", 0.0)
                net_amount += count * unit_cost
                lines.append({
                    "item_sku": sku,
                    "title": item.get("item_title", sku),
                    "count": count,
                    "cost": unit_cost
                })

            dur = (time.time() - start_t) * 1000
            return ToolExecutionResult(
                action_id=action_id,
                tool_id="beta_tool_view_basket",
                provider_id="provider_beta",
                tool_name=tool_name,
                status="SUCCESS",
                payload={
                    "session_id": sess_id,
                    "version": basket["version"],
                    "lines": lines,
                    "net_amount": net_amount
                },
                verified_postcondition=True,
                verification_details=f"Verified ElectroStore basket state: {len(lines)} lines, net ₹{net_amount:,.2f}.",
                execution_time_ms=round(dur, 2)
            )

        dur = (time.time() - start_t) * 1000
        return ToolExecutionResult(
            action_id=action_id,
            tool_id="unknown",
            provider_id="provider_beta",
            tool_name=tool_name,
            status="FAILED",
            error_message=f"Tool '{tool_name}' unsupported on ElectroStore Pro.",
            execution_time_ms=round(dur, 2)
        )

    def get_health(self) -> ProviderHealth:
        return self._provider_info.health


class ProviderGammaAdapter(BaseProviderAdapter):
    """Provider Gamma (Simulated Failure Store).

    Used to test automatic router failover, resilience, and recovery.
    """

    def __init__(self, simulate_failure: bool = True):
        self.simulate_failure = simulate_failure
        self._provider_info = ProviderInfo(
            provider_id="provider_gamma",
            name="FaultyStore Global",
            description="Simulated unmaintained remote store for testing error recovery.",
            provider_type=ProviderType.REMOTE_MCP,
            origin_url="https://gamma.faulty.example.com",
            supported_capabilities=[CanonicalCapability.PRODUCT_SEARCH],
            health=ProviderHealth.DEGRADED if simulate_failure else ProviderHealth.HEALTHY,
            data_quality_score=0.40,
            historical_reliability=0.20,
            average_latency_ms=850.0
        )

    @property
    def provider_info(self) -> ProviderInfo:
        return self._provider_info

    def discover_tools(self) -> List[ToolDefinition]:
        return [
            ToolDefinition(
                tool_id="gamma_tool_search",
                provider_id="provider_gamma",
                tool_name="catalog_search",
                description="Query FaultyStore catalog (simulates network timeout/503).",
                input_schema={
                    "type": "object",
                    "properties": {
                        "filter_dict": {"type": "object"}
                    },
                    "required": ["filter_dict"]
                },
                canonical_capability=CanonicalCapability.PRODUCT_SEARCH,
                classification=ToolClassification.READ_ONLY,
                requires_user_approval=False,
                execution_mode=ExecutionMode.REMOTE_MCP
            )
        ]

    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> ToolExecutionResult:
        action_id = f"act_gamma_{uuid.uuid4().hex[:8]}"
        if self.simulate_failure:
            return ToolExecutionResult(
                action_id=action_id,
                tool_id="gamma_tool_search",
                provider_id="provider_gamma",
                tool_name=tool_name,
                status="FAILED",
                error_message="Connection timed out: Remote MCP server 503 Service Unavailable.",
                execution_time_ms=850.0
            )

        return ToolExecutionResult(
            action_id=action_id,
            tool_id="gamma_tool_search",
            provider_id="provider_gamma",
            tool_name=tool_name,
            status="SUCCESS",
            payload={"results": []},
            verified_postcondition=True,
            execution_time_ms=100.0
        )

    def get_health(self) -> ProviderHealth:
        return self._provider_info.health
