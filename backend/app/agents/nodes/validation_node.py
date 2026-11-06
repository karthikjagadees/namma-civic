"""
Namma Civic — Validation Agent Node
Assesses complaint authenticity, detects spam/gibberish, and validates location feasibility.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List

from app.agents.state import CivicActionState

logger = logging.getLogger("namma-civic.agent.validation")

SPAM_PATTERNS = [
    r"^[a-zA-Z]{1,4}$",  # ultra-short gibberish
    r"(.)\1{4,}",        # repeated characters e.g. "aaaaaa", "xxxxxx"
    r"\b(test|testing|fake|asdf|qwerty)\b",
    r"\b(crypto|casino|bitcoin|viagra|loan offer)\b",
]

CIVIC_KEYWORDS = {
    "road", "pothole", "tar", "street", "pipe", "water", "leak", "garbage",
    "trash", "light", "lamp", "drain", "sewage", "manhole", "traffic",
    "signal", "encroach", "sidewalk", "footpath", "park", "tree", "wire", "cable"
}


async def validation_node(state: CivicActionState) -> Dict[str, Any]:
    """
    Validation node: Checks whether a complaint is authentic, non-spam, and actionable.
    """
    logger.info(f"[ValidationAgent] Validating complaint: {state.get('complaint_id')}")

    title = (state.get("title") or "").strip()
    description = (state.get("description") or "").strip()
    combined_text = f"{title} {description}".lower()

    flags: List[str] = []
    spam_score = 0.0

    # 1. Spam / Gibberish checks
    for pat in SPAM_PATTERNS:
        if re.search(pat, combined_text, re.IGNORECASE):
            spam_score += 0.4
            flags.append("spam_pattern_matched")

    if len(combined_text.split()) < 3:
        spam_score += 0.3
        flags.append("insufficient_detail")

    # 2. Actionability: Civic keyword matching
    has_civic_reference = any(kw in combined_text for kw in CIVIC_KEYWORDS)
    if not has_civic_reference:
        spam_score += 0.2
        flags.append("weak_civic_context")
    else:
        flags.append("civic_context_verified")

    # 3. Location validity
    lat = state.get("latitude")
    lon = state.get("longitude")
    has_valid_coords = False
    if lat is not None and lon is not None:
        if -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0:
            has_valid_coords = True
            flags.append("valid_coordinates")
        else:
            flags.append("invalid_coordinates")
    else:
        flags.append("missing_coordinates")

    # 4. Multimodal alignment
    intake = state.get("intake_result", {})
    confidence = intake.get("confidence_score", 0.8)
    if confidence < 0.6:
        spam_score += 0.2
        flags.append("low_ai_confidence")

    is_valid = spam_score < 0.6
    validity_reason = (
        "Report verified as legitimate civic infrastructure grievance."
        if is_valid
        else f"Validation failed due to suspected spam or invalid data ({', '.join(flags)})."
    )

    validation_result = {
        "is_valid": is_valid,
        "spam_score": round(min(spam_score, 1.0), 2),
        "validity_reason": validity_reason,
        "is_actionable": is_valid and has_civic_reference,
        "flags": flags,
    }

    steps = list(state.get("steps_completed", []))
    if "validation" not in steps:
        steps.append("validation")

    return {
        "validation_result": validation_result,
        "current_step": "deduplication" if is_valid else "approval",
        "steps_completed": steps,
    }
