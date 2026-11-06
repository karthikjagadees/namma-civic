"""Expose the visual findings already produced by multimodal intake."""
from __future__ import annotations

from typing import Any, Dict

from app.agents.state import CivicActionState


async def vision_node(state: CivicActionState) -> Dict[str, Any]:
    """Forward intake's image analysis as a named stage, without another AI call."""
    intake = state.get("intake_result", {})
    analysis = intake.get("vision_analysis")
    result = {
        "available": bool(analysis),
        "analysis": analysis,
        "source": "mock_or_configured_intake_provider" if analysis else "no_image_analysis",
    }
    steps = list(state.get("steps_completed", []))
    if "vision" not in steps:
        steps.append("vision")
    return {"vision_result": result, "current_step": "validation", "steps_completed": steps}
