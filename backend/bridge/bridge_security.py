"""Security and Origin Validation for WebMCP Browser Bridge."""
import re
from urllib.parse import urlparse
from typing import Any, Dict, List, Optional


class BridgeSecurityManager:
    # Explicit allowed origins (scheme + host + optional port)
    ALLOWED_ORIGINS = {
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://techmart.example.com",
        "https://electrostore.example.com",
        "https://webpilot.store",
        "https://asi1.ai",
        "https://agentverse.ai"
    }

    ALLOWED_HOSTNAMES = {
        "localhost",
        "127.0.0.1",
        "techmart.example.com",
        "electrostore.example.com",
        "webpilot.store",
        "asi1.ai",
        "agentverse.ai"
    }

    @classmethod
    def validate_origin(cls, origin: str) -> bool:
        if not origin:
            return True  # Internal / in-process execution

        clean = origin.rstrip("/")
        if clean in cls.ALLOWED_ORIGINS:
            return True

        try:
            parsed = urlparse(clean)
            if not parsed.scheme or not parsed.hostname:
                return False
            # Check exact hostname match (not substring!)
            if parsed.hostname in cls.ALLOWED_HOSTNAMES:
                return True
        except Exception:
            return False

        return False

    @classmethod
    def sanitize_arguments(cls, args: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize arguments and neutralize adversarial prompt injections."""
        sanitized = {}
        injection_patterns = [
            r"(?i)ignore\s+all\s+(prior|previous)\s+instructions",
            r"(?i)system\s+prompt\s+override",
            r"(?i)bypass\s+(approval|policy|security)",
            r"(?i)execute\s+checkout\s+immediately",
            r"(?i)grant\s+admin\s+privileges"
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
