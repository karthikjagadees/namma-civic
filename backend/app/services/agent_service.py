"""
Namma Civic — Multi-Agent Orchestration Service
Coordinates LangGraph execution, checkpoint persistence, and human-in-the-loop decisions.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.graph import civic_action_graph
from app.agents.state import CivicActionState
from app.models.complaint import Complaint
from app.schemas.agent import OfficerApprovalRequest

logger = logging.getLogger("namma-civic.service.agents")


class AgentService:
    @staticmethod
    async def orchestrate_complaint(
        complaint_id: str,
        session: AsyncSession,
    ) -> Dict[str, Any]:
        """
        Launches or advances the LangGraph multi-agent pipeline for a complaint.
        Persists state under thread_id = complaint_id.
        """
        stmt = (
            select(Complaint)
            .where(Complaint.id == complaint_id)
            .options(selectinload(Complaint.media), selectinload(Complaint.timeline))
        )
        res = await session.execute(stmt)
        complaint = res.scalar_one_or_none()
        if not complaint:
            raise ValueError(f"Complaint {complaint_id} not found")

        config = {"configurable": {"thread_id": complaint_id}}

        # Check if already in progress or checkpointed
        state_snapshot = civic_action_graph.get_state(config)
        if state_snapshot and state_snapshot.values and state_snapshot.values.get("steps_completed"):
            logger.info(f"Resuming existing graph state for {complaint_id}")
            # If already completed, return cached values
            if "action" in state_snapshot.values.get("steps_completed", []):
                return state_snapshot.values
            result = await civic_action_graph.ainvoke(None, config=config)
            return result

        # Initialize fresh state
        media_urls = [m.file_url for m in complaint.media]
        photo_hashes = [
            m.perceptual_hash for m in complaint.media
            if m.media_type.value == "image" and m.perceptual_hash
        ]
        initial_state: CivicActionState = {
            "complaint_id": complaint.id,
            "citizen_id": complaint.citizen_id,
            "title": complaint.title,
            "description": complaint.description,
            "category": complaint.category.value,
            "latitude": complaint.latitude,
            "longitude": complaint.longitude,
            "location_accuracy_m": complaint.location_accuracy_m,
            "location_confidence": complaint.location_confidence,
            "address": complaint.address,
            "landmark": complaint.landmark,
            "media_urls": media_urls,
            "photo_hashes": photo_hashes,
            "source": complaint.source.value,
            "reported_at": complaint.created_at,
            "requires_human_approval": False,
            "approval_reason": "",
            "is_awaiting_approval": False,
            "human_decision": None,
            "current_step": "intake",
            "steps_completed": [],
            "errors": [],
        }

        logger.info(f"Starting fresh LangGraph run for {complaint_id}")
        result = await civic_action_graph.ainvoke(initial_state, config=config)
        return result

    @staticmethod
    async def get_agent_state(
        complaint_id: str,
        session: AsyncSession,
    ) -> Dict[str, Any]:
        """
        Fetches the current LangGraph execution snapshot for a complaint.
        If no run exists yet, initiates one.
        """
        config = {"configurable": {"thread_id": complaint_id}}
        snapshot = civic_action_graph.get_state(config)
        if snapshot and snapshot.values:
            return snapshot.values

        # If not started, trigger initial orchestration
        return await AgentService.orchestrate_complaint(complaint_id, session)

    @staticmethod
    async def submit_human_decision(
        complaint_id: str,
        approval_req: OfficerApprovalRequest,
        officer_id: str,
        session: AsyncSession,
    ) -> Dict[str, Any]:
        """
        Submits human officer approval, rejection, or field overrides, and resumes the graph.
        """
        config = {"configurable": {"thread_id": complaint_id}}

        # Ensure graph was started
        snapshot = civic_action_graph.get_state(config)
        if not snapshot or not snapshot.values:
            await AgentService.orchestrate_complaint(complaint_id, session)

        decision = {
            "approved": approval_req.approved,
            "officer_id": officer_id,
            "officer_notes": approval_req.officer_notes or ("Approved by officer." if approval_req.approved else "Rejected by officer."),
            "override_dept": approval_req.override_dept,
            "override_priority": approval_req.override_priority,
        }

        logger.info(f"Applying officer decision to paused graph for {complaint_id}: {decision}")
        # Update state and resume
        resume_payload = {
            "human_decision": decision,
            "is_awaiting_approval": False,
        }
        result = await civic_action_graph.ainvoke(resume_payload, config=config)
        return result
