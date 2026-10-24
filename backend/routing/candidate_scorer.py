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
    """Score a candidate product using normalized numeric features and priority weights."""
    priorities = [p.lower() for p in (priorities or [])]
    specs = product.specs

    # Extract numeric features
    cpu_cores = parse_numeric_cpu_cores(specs.cpu)
    ram_gb = parse_numeric_ram_gb(specs.ram)
    battery_wh = parse_numeric_battery_wh(specs.battery)
    warranty_yrs = parse_numeric_warranty_years(specs.warranty)

    # Provider reliability lookup
    provider_info = provider_registry.get_provider(product.provider_id)
    provider_rel = getattr(provider_info, "historical_reliability", 0.95) if provider_info else 0.8
    provider_health = 1.0 if (provider_info and getattr(provider_info.health, "value", provider_info.health) == "healthy") else 0.5

    # Feature normalization to [0.0, 1.0]
    # CPU: 4 to 16 cores -> normalized
    norm_cpu = min(max((cpu_cores - 4.0) / 10.0, 0.0), 1.0)
    # RAM: 8 to 32 GB
    norm_ram = min(max((ram_gb - 8.0) / 24.0, 0.0), 1.0)
    # Battery: 40 to 80 Wh; penalty for unknown
    if battery_wh is not None:
        norm_battery = min(max((battery_wh - 40.0) / 40.0, 0.0), 1.0)
    else:
        norm_battery = 0.15  # Transparent penalty for unknown spec

    # Warranty: 1 to 3 years; penalty for unknown
    if warranty_yrs is not None:
        norm_warranty = min(max((warranty_yrs - 1.0) / 2.0, 0.0), 1.0)
    else:
        norm_warranty = 0.1  # Transparent penalty for unknown spec

    # Price efficiency / headroom
    if budget and budget > 0:
        norm_price = max(0.0, min(1.0, 1.0 - (product.price / budget)))
    else:
        norm_price = 0.5

    # Rating (0 to 5)
    norm_rating = min(max(product.rating / 5.0, 0.0), 1.0)

    # Dynamic Weight Assignment based on User Priorities
    # Baseline weights
    w_cpu = 0.22
    w_ram = 0.16
    w_battery = 0.20
    w_warranty = 0.12
    w_reliability = 0.15
    w_price = 0.15

    if "coding" in priorities or "programming" in priorities:
        w_cpu = 0.40
        w_ram = 0.25
        w_battery = 0.12
        w_warranty = 0.08
        w_reliability = 0.05
        w_price = 0.10
    elif "battery" in priorities or "endurance" in priorities:
        w_battery = 0.45
        w_cpu = 0.15
        w_ram = 0.10
        w_warranty = 0.08
        w_reliability = 0.10
        w_price = 0.12
    elif "reliability" in priorities or "durable" in priorities:
        w_warranty = 0.35
        w_reliability = 0.30
        w_cpu = 0.12
        w_battery = 0.08
        w_ram = 0.05
        w_price = 0.10

    # Total weighted sum
    composite = (
        (norm_cpu * w_cpu) +
        (norm_ram * w_ram) +
        (norm_battery * w_battery) +
        (norm_warranty * w_warranty) +
        (provider_rel * provider_health * w_reliability) +
        (norm_price * w_price)
    )

    # Scale to 50.0 - 98.0 range for readable UI display
    final_score = 50.0 + (composite * 48.0)
    return round(final_score, 1)
