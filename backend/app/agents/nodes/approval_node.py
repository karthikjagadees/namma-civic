"""
Namma Civic — Human-in-the-Loop (HITL) Approval Agent Node
Pauses execution for officer review, processes human approvals, rejections, and overrides.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from app.agents.state import CivicActionState

logger = logging.getLogger("namma-civic.agent.approval")


async def approval_node(state: CivicActionState) -> Dict[str, Any]:
    """
    Approval node: Evaluates human officer decision or pauses execution awaiting review.
    """
    complaint_id = state.get("complaint_id")
    human_decision = state.get("human_decision")
    logger.info(f"[ApprovalAgent] Evaluating decision for complaint {complaint_id}: {human_decision}")

    steps = list(state.get("steps_completed", []))
    if "approval" not in steps:
        steps.append("approval")

    # If no decision has been submitted yet, keep in awaiting approval state
    if not human_decision:
        logger.info(f"[ApprovalAgent] Complaint {complaint_id} is awaiting human officer review.")
        return {
            "is_awaiting_approval": True,
            "current_step": "approval",
            "steps_completed": steps,
        }

    approved = human_decision.get("approved", True)
    officer_notes = human_decision.get("officer_notes", "")
    override_dept = human_decision.get("override_dept")
    override_priority = human_decision.get("override_priority")

    routing_result = dict(state.get("routing_result", {}))
    if override_dept:
        routing_result["department_code"] = override_dept
        routing_result["department_name"] = f"Department ({override_dept})"
    if override_priority:
        routing_result["priority"] = override_priority

    if approved:
        logger.info(f"[ApprovalAgent] Complaint {complaint_id} APPROVED by officer. Proceeding to action.")
        return {
            "is_awaiting_approval": False,
            "routing_result": routing_result,
            "current_step": "action",
            "steps_completed": steps,
        }
    else:
        logger.info(f"[ApprovalAgent] Complaint {complaint_id} REJECTED by officer ({officer_notes}). Concluding.")
        return {
            "is_awaiting_approval": False,
            "action_result": {
                "work_order_id": "REJECTED",
                "action_status": "rejected",
                "dispatched_to": "None",
                "notifications_queued": True,
                "timeline_note": f"Rejected during officer review: {officer_notes}",
            },
            "current_step": "completed",
            "steps_completed": steps,
        }
