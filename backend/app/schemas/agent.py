"""
Namma Civic — Agent API Schemas
Pydantic schemas for LangGraph orchestration, state inspection, and officer approval.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class OfficerApprovalRequest(BaseModel):
    approved: bool = Field(True, description="Whether officer approves the dispatch")
    officer_notes: Optional[str] = Field("", description="Reason or additional instructions")
    override_dept: Optional[str] = Field(None, description="Override target department code (e.g. ROADS, WATER)")
    override_priority: Optional[str] = Field(None, description="Override priority level (low, medium, high, critical)")


class AgentOrchestrateResponse(BaseModel):
    complaint_id: str
    current_step: str
    steps_completed: List[str]
    requires_human_approval: bool
    is_awaiting_approval: bool
    approval_reason: Optional[str] = None
    intake_result: Optional[Dict[str, Any]] = None
    validation_result: Optional[Dict[str, Any]] = None
    deduplication_result: Optional[Dict[str, Any]] = None
    routing_result: Optional[Dict[str, Any]] = None
    action_result: Optional[Dict[str, Any]] = None
    human_decision: Optional[Dict[str, Any]] = None
