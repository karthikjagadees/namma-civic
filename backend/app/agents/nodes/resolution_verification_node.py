"""Run the existing resolution evidence checker when evidence is explicitly supplied."""
from __future__ import annotations

from typing import Any, Dict

from app.agents.state import CivicActionState
from app.core.database import async_session_factory
from app.services.verification_service import ResolutionVerificationService


async def resolution_verification_node(state: CivicActionState) -> Dict[str, Any]:
    """Delegate supplied field evidence to the existing verification service."""
    notes = state.get("resolution_notes")
    image_url = state.get("resolution_image_url")
    if not notes and not image_url:
        result: Dict[str, Any] = {"status": "not_requested"}
    else:
        async with async_session_factory() as session:
            result = await ResolutionVerificationService.verify_resolution_evidence(
                session=session,
                complaint_id=state["complaint_id"],
                resolution_notes=notes or "",
                resolution_image_url=image_url,
                officer_id=state.get("verification_officer_id"),
            )
    steps = list(state.get("steps_completed", []))
    if "resolution_verification" not in steps:
        steps.append("resolution_verification")
    return {"verification_result": result, "current_step": "completed", "steps_completed": steps}
