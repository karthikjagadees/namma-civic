"""
Namma Civic — LangGraph Multi-Agent State
Defines the shared state passed across all agent nodes during civic action orchestration.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict


class CivicActionState(TypedDict, total=False):
    # Core complaint metadata
    complaint_id: str
    citizen_id: str
    title: str
    description: str
    category: str
    latitude: Optional[float]
    longitude: Optional[float]
    address: Optional[str]
    landmark: Optional[str]
    media_urls: List[str]
    photo_hashes: List[str]
    source: str
    location_accuracy_m: Optional[float]
    location_confidence: Optional[float]

    # Node outputs
    intake_result: Dict[str, Any]
    # {summary, detected_category, confidence_score, urgency_score, severity, extracted_entities, vision_analysis}

    validation_result: Dict[str, Any]
    # {is_valid: bool, spam_score: float, validity_reason: str, is_actionable: bool, flags: List[str]}

    deduplication_result: Dict[str, Any]
    # {decision, incident_id, recurrence_of_incident_id, ranked_candidates, failures}

    routing_result: Dict[str, Any]
    # {department_id: str, department_name: str, department_code: str, priority: str, severity: int, sla_hours: int, routing_rationale: str}

    vision_result: Dict[str, Any]
    priority_result: Dict[str, Any]
    incident_report_count: int
    monitoring_result: Dict[str, Any]
    sla_snapshot: Dict[str, Any]
    resolution_notes: str
    resolution_image_url: Optional[str]
    verification_officer_id: Optional[str]
    verification_result: Dict[str, Any]

    # Human-in-the-Loop (HITL) Gate
    requires_human_approval: bool
    approval_reason: str
    is_awaiting_approval: bool
    human_decision: Optional[Dict[str, Any]]
    # {approved: bool, officer_id: Optional[str], officer_notes: str, override_dept: Optional[str], override_priority: Optional[str], timestamp: str}

    # Final Action Execution
    action_result: Dict[str, Any]
    # {work_order_id: str, action_status: str, notifications_queued: bool, dispatched_to: str, timeline_note: str}

    # Workflow tracing
    current_step: str
    steps_completed: List[str]
    errors: List[str]
