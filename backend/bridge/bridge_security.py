"""Security and Origin Validation for WebMCP Browser Bridge."""
import re
from typing import Any, Dict, List, Optional


class BridgeSecurityManager:
    ALLOWED_ORIGINS = {
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://techmart.example.com",
        "https://electrostore.example.com",
        "https://webpilot.store"
    }

    @classmethod
    def validate_origin(cls, origin: str) -> bool:
        if not origin:
            return True  # Local / in-process execution
        clean_origin = origin.rstrip("/")
        # Allow any local or allowed origin
        if clean_origin in cls.ALLOWED_ORIGINS or "localhost" in clean_origin or "127.0.0.1" in clean_origin:
            return True
        return False

    @classmethod
    def sanitize_arguments(cls, args: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize arguments and neutralize adversarial prompt injections."""
        sanitized = {}
        injection_patterns = [
            r"(?i)ignore\s+all\s+(prior|previous)\s+instructions",
            r"(?i)bypass\s+(approval|policy|security)",
            r"(?i)execute\s+checkout\s+immediately"
        ]

        for k, v in args.items():
            if isinstance(v, str):
                cleaned = v
                for pat in injection_patterns:
                    if re.search(pat, cleaned):
                        cleaned = re.sub(pat, "[FILTERED_ATTEMPT]", cleaned)
                sanitized[k] = cleaned
            elif isinstance(v, dict):
                sanitized[k] = cls.sanitize_arguments(v)
            else:
                sanitized[k] = v

        return sanitized
