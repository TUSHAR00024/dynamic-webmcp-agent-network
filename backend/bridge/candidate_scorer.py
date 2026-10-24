"""Bridge candidate scorer module with query sanitization helper."""
import re
from typing import Any, Dict, List, Optional
from backend.routing.candidate_scorer import score_candidate, calculate_candidate_score, sanitize_user_query

__all__ = ["sanitize_user_query", "score_candidate", "calculate_candidate_score"]
