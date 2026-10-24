"""Normalized numeric candidate scoring engine with dynamic priority weighting."""
import re
from typing import Any, Dict, List, Optional
from backend.models.product import ProductRecord
from backend.registry.provider_registry import provider_registry


def parse_numeric_ram_gb(ram_str: str) -> float:
    """Extract RAM size in GB from text."""
    match = re.search(r"(\d+)\s*gb", ram_str.lower())
    if match:
        return float(match.group(1))
    return 8.0  # default baseline


def parse_numeric_battery_wh(bat_str: str) -> Optional[float]:
    """Extract battery capacity in Wh or convert estimated hours."""
    b_lower = bat_str.lower()
    if "unknown" in b_lower:
        return None
    wh_match = re.search(r"(\d+(?:\.\d+)?)\s*wh", b_lower)
    if wh_match:
        return float(wh_match.group(1))
    hr_match = re.search(r"(\d+(?:\.\d+)?)\s*hours?", b_lower)
    if hr_match:
        # Approximate 1 hour productivity ~ 6.0 Wh
        return float(hr_match.group(1)) * 6.0
    return None


def parse_numeric_cpu_cores(cpu_str: str) -> float:
    """Extract CPU cores or tier strength."""
    c_lower = cpu_str.lower()
    cores_match = re.search(r"(\d+)\s*cores?", c_lower)
    if cores_match:
        return float(cores_match.group(1))
    if any(k in c_lower for k in ["ryzen 7", "i7", "13500h", "m2", "m3"]):
        return 8.0
    if any(k in c_lower for k in ["ryzen 5", "i5"]):
        return 6.0
    return 4.0


def parse_numeric_warranty_years(war_str: str) -> Optional[float]:
    """Extract warranty duration in years."""
    w_lower = war_str.lower()
    if "unknown" in w_lower:
        return None
    yr_match = re.search(r"(\d+)\s*[- ]?years?", w_lower)
    if yr_match:
        return float(yr_match.group(1))
    if "onsite" in w_lower or "standard" in w_lower:
        return 1.0
    return None


def score_candidate(
    product: ProductRecord,
    budget: Optional[float] = None,
    priorities: Optional[List[str]] = None
) -> float:
    """Score a candidate product using normalized numeric features and domain-adaptive priority weights."""
    priorities = [p.lower() for p in (priorities or [])]
    specs = product.specs

    # Provider reliability lookup
    provider_info = provider_registry.get_provider(product.provider_id)
    provider_rel = getattr(provider_info, "historical_reliability", 0.95) if provider_info else 0.8
    provider_health = 1.0 if (provider_info and getattr(provider_info.health, "value", provider_info.health) == "healthy") else 0.5

    # Price efficiency / headroom
    if budget and budget > 0:
        norm_price = max(0.0, min(1.0, 1.0 - (product.price / budget)))
    else:
        norm_price = 0.5

    norm_rating = min(max(product.rating / 5.0, 0.0), 1.0)
    category = getattr(specs, "category", "") or getattr(product, "category", "general")

    # Domain 1: Laptops & Computers (standard CPU/RAM/Battery spec sheet)
    is_laptop = (specs.cpu != "unknown" or specs.ram != "unknown" or category == "laptops")
    if is_laptop:
        cpu_cores = parse_numeric_cpu_cores(specs.cpu)
        ram_gb = parse_numeric_ram_gb(specs.ram)
        battery_wh = parse_numeric_battery_wh(specs.battery)
        warranty_yrs = parse_numeric_warranty_years(specs.warranty)

        norm_cpu = min(max((cpu_cores - 4.0) / 10.0, 0.0), 1.0)
        norm_ram = min(max((ram_gb - 8.0) / 24.0, 0.0), 1.0)
        norm_battery = min(max((battery_wh - 40.0) / 40.0, 0.0), 1.0) if battery_wh is not None else 0.15
        norm_warranty = min(max((warranty_yrs - 1.0) / 2.0, 0.0), 1.0) if warranty_yrs is not None else 0.1

        w_cpu, w_ram, w_battery, w_warranty, w_reliability, w_price = 0.22, 0.16, 0.20, 0.12, 0.15, 0.15
        if "coding" in priorities or "programming" in priorities:
            w_cpu, w_ram, w_battery, w_warranty, w_reliability, w_price = 0.40, 0.25, 0.12, 0.08, 0.05, 0.10
        elif "battery" in priorities or "endurance" in priorities:
            w_battery, w_cpu, w_ram, w_warranty, w_reliability, w_price = 0.45, 0.15, 0.10, 0.08, 0.10, 0.12
        elif "reliability" in priorities or "durable" in priorities:
            w_warranty, w_reliability, w_cpu, w_battery, w_ram, w_price = 0.35, 0.30, 0.12, 0.08, 0.05, 0.10

        composite = (
            (norm_cpu * w_cpu) +
            (norm_ram * w_ram) +
            (norm_battery * w_battery) +
            (norm_warranty * w_warranty) +
            (provider_rel * provider_health * w_reliability) +
            (norm_price * w_price)
        )
        final_score = 50.0 + (composite * 48.0)
        return round(final_score, 1)

    # Domain 2: Computer Monitors
    if category == "monitors" or specs.get("refresh_rate") or specs.get("resolution"):
        rr_str = str(specs.get("refresh_rate", "60hz")).lower()
        rr_num = 60.0
        m = re.search(r"(\d+)\s*hz", rr_str)
        if m:
            rr_num = float(m.group(1))
        norm_rr = min(max((rr_num - 60.0) / 180.0, 0.0), 1.0)

        res_str = str(specs.get("resolution", "")).lower()
        norm_res = 1.0 if "4k" in res_str or "2160" in res_str else (0.75 if "qhd" in res_str or "1440" in res_str else 0.5)
        norm_warranty = 1.0 if "3-year" in str(specs.get("warranty", "")).lower() else 0.5

        w_rr, w_res, w_warranty, w_rating, w_price = 0.25, 0.25, 0.15, 0.20, 0.15
        if "gaming" in priorities or "refresh" in priorities:
            w_rr, w_res, w_price = 0.50, 0.15, 0.05
        elif "designer" in priorities or "color" in priorities or "4k" in priorities:
            w_res, w_rr, w_price = 0.60, 0.05, 0.05

        composite = (norm_rr * w_rr) + (norm_res * w_res) + (norm_warranty * w_warranty) + (norm_rating * w_rating) + (norm_price * w_price)
        final_score = 50.0 + (composite * 48.0)
        return round(final_score, 1)

    # Domain 3: Office Furniture
    if category == "furniture" or specs.get("ergonomics") or specs.get("material"):
        war_str = str(specs.get("warranty") or specs.get("guarantee", "")).lower()
        norm_war = 1.0 if "12-year" in war_str else (0.7 if "3-year" in war_str else 0.4)
        norm_ergo = 0.9 if "lumbar" in str(specs.get("ergonomics", "")).lower() else 0.6

        composite = (norm_ergo * 0.35) + (norm_war * 0.25) + (norm_rating * 0.20) + (norm_price * 0.20)
        final_score = 50.0 + (composite * 48.0)
        return round(final_score, 1)

    # Domain 4: Cloud Services & Software Subscriptions
    if category in ("cloud_services", "software_subscriptions") or specs.get("uptime_sla") or specs.get("licenses"):
        norm_sla = 1.0 if "99.99" in str(specs.get("uptime_sla", "")) else 0.8
        composite = (norm_sla * 0.30) + (norm_rating * 0.30) + (provider_rel * provider_health * 0.20) + (norm_price * 0.20)
        final_score = 50.0 + (composite * 48.0)
        return round(final_score, 1)

    # General Open-Domain Fallback
    composite = (norm_rating * 0.35) + (provider_rel * provider_health * 0.25) + (norm_price * 0.25) + 0.15
    final_score = 50.0 + (composite * 48.0)
    return round(final_score, 1)


def sanitize_user_query(raw_query: str) -> str:
    """Strip platform tags, handles, and prefixes (e.g., @webmcp, webmcp:) from user query."""
    cleaned = re.sub(r'@\w+\s*', '', raw_query).strip()
    cleaned = re.sub(r'^webmcp[:\s]*', '', cleaned, flags=re.IGNORECASE).strip()
    return cleaned if cleaned else "general products"



calculate_candidate_score = score_candidate

