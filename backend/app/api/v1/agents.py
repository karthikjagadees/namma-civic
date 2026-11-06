"""
Namma Civic — Multi-Agent API Router (Phase 5)
Exposes LangGraph orchestration, state inspection, and Human-in-the-Loop decision endpoints.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, RequireOfficer, require_complaint_access
from app.core.database import get_db
from app.models.user import User, UserRole
from app.schemas.agent import AgentOrchestrateResponse, OfficerApprovalRequest
from app.services.agent_service import AgentService

logger = logging.getLogger("namma-civic.api.agents")

router = APIRouter(prefix="/agents", tags=["LangGraph Multi-Agent Orchestration"])


@router.post("/orchestrate/{complaint_id}", response_model=AgentOrchestrateResponse, status_code=status.HTTP_200_OK)
async def orchestrate_complaint_pipeline(
    complaint_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> AgentOrchestrateResponse:
    """
    Launch or advance the LangGraph multi-agent orchestration for a civic complaint.
    Executes Intake -> Validation -> Deduplication -> Routing -> (HITL Approval Gate) -> Action Dispatch.
    """
    await require_complaint_access(db, complaint_id, current_user)
    try:
        result = await AgentService.orchestrate_complaint(complaint_id, db)
        return AgentOrchestrateResponse(
            complaint_id=complaint_id,
            current_step=result.get("current_step", "completed"),
            steps_completed=result.get("steps_completed", []),
            requires_human_approval=result.get("requires_human_approval", False),
            is_awaiting_approval=result.get("is_awaiting_approval", False),
            approval_reason=result.get("approval_reason"),
            intake_result=result.get("intake_result"),
            validation_result=result.get("validation_result"),
            deduplication_result=result.get("deduplication_result"),
            routing_result=result.get("routing_result"),
            action_result=result.get("action_result"),
            human_decision=result.get("human_decision"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.error(f"Error orchestrating agents for {complaint_id}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Multi-agent execution failed: {str(exc)}",
        )


@router.get("/state/{complaint_id}", response_model=AgentOrchestrateResponse, status_code=status.HTTP_200_OK)
async def get_complaint_agent_state(
    complaint_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> AgentOrchestrateResponse:
    """
    Retrieve the current LangGraph execution snapshot and node progression.
    """
    await require_complaint_access(db, complaint_id, current_user)
    try:
        result = await AgentService.get_agent_state(complaint_id, db)
        return AgentOrchestrateResponse(
            complaint_id=complaint_id,
            current_step=result.get("current_step", "completed"),
            steps_completed=result.get("steps_completed", []),
            requires_human_approval=result.get("requires_human_approval", False),
            is_awaiting_approval=result.get("is_awaiting_approval", False),
            approval_reason=result.get("approval_reason"),
            intake_result=result.get("intake_result"),
            validation_result=result.get("validation_result"),
            deduplication_result=result.get("deduplication_result"),
            routing_result=result.get("routing_result"),
            action_result=result.get("action_result"),
            human_decision=result.get("human_decision"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.error(f"Error getting agent state for {complaint_id}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve agent state: {str(exc)}",
        )


@router.post("/approve/{complaint_id}", response_model=AgentOrchestrateResponse, status_code=status.HTTP_200_OK)
async def submit_officer_approval(
    complaint_id: str,
    body: OfficerApprovalRequest,
    current_user: RequireOfficer,
    db: AsyncSession = Depends(get_db),
) -> AgentOrchestrateResponse:
    """
    Submit Human-in-the-Loop officer decision (Approve, Reject, Override Department/Priority).
    Resumes graph execution from paused approval node.
    """
    try:
        result = await AgentService.submit_human_decision(
            complaint_id=complaint_id,
            approval_req=body,
            officer_id=current_user.id,
            session=db,
        )
        return AgentOrchestrateResponse(
            complaint_id=complaint_id,
            current_step=result.get("current_step", "completed"),
            steps_completed=result.get("steps_completed", []),
            requires_human_approval=result.get("requires_human_approval", False),
            is_awaiting_approval=result.get("is_awaiting_approval", False),
            approval_reason=result.get("approval_reason"),
            intake_result=result.get("intake_result"),
            validation_result=result.get("validation_result"),
            deduplication_result=result.get("deduplication_result"),
            routing_result=result.get("routing_result"),
            action_result=result.get("action_result"),
            human_decision=result.get("human_decision"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.error(f"Error resuming graph with decision for {complaint_id}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Approval resolution failed: {str(exc)}",
        )
