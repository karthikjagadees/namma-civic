# Namma Civic — LangGraph Multi-Agent System

## Overview

Namma Civic uses [LangGraph](https://langchain-ai.github.io/langgraph/) to orchestrate 10 specialized agents via a supervisor pattern.

## Namma CivicState

```python
class Namma CivicState(TypedDict):
    complaint_id: str
    raw_text: str
    raw_image_url: Optional[str]
    raw_audio_url: Optional[str]

    # After Intake Agent
    parsed_text: Optional[str]
    detected_language: Optional[str]

    # After Vision Agent
    image_analysis: Optional[dict]

    # After Location Agent
    latitude: Optional[float]
    longitude: Optional[float]
    address: Optional[str]
    jurisdiction: Optional[str]

    # After Validation Agent
    is_valid: Optional[bool]
    validation_errors: List[str]
    requires_human_review: bool

    # After Duplicate Agent
    duplicate_matches: List[dict]
    is_duplicate: bool
    primary_complaint_id: Optional[str]

    # After Priority Agent
    severity_score: Optional[float]
    safety_score: Optional[float]
    urgency_score: Optional[float]
    population_impact: Optional[float]
    final_priority_score: Optional[float]
    priority_level: Optional[str]  # LOW/MEDIUM/HIGH/CRITICAL
    priority_explanation: Optional[str]

    # After Routing Agent
    department_id: Optional[str]
    department_name: Optional[str]
    routing_confidence: Optional[float]
    routing_reason: Optional[str]

    # After Action Agent
    civic_task_id: Optional[str]
    action_taken: Optional[str]

    # After Monitoring Agent
    sla_deadline: Optional[str]
    sla_status: Optional[str]

    # After Resolution Agent
    resolution_confidence: Optional[float]
    resolution_verified: Optional[bool]

    # Metadata
    messages: List[dict]
    agent_trace: List[dict]
    error: Optional[str]
    current_agent: Optional[str]
```

## Agent Descriptions

### 1. Intake Agent
- Parses raw text/voice input
- Detects language
- Extracts key entities (location mentions, issue type)
- Calls AI provider for structured extraction

### 2. Vision Agent
- Analyses uploaded image via multimodal LLM
- Detects issue category from image
- Estimates severity from visual evidence
- Validates image relevance

### 3. Location Agent
- Geocodes address/coordinates
- Identifies jurisdictional boundary
- Finds nearest civic zone

### 4. Validation Agent
- Checks completeness of report
- Validates location falls within service area
- Flags low-quality or incomplete reports
- Routes to human review if needed

### 5. Duplicate Detection Agent
- Searches nearby complaints (GeoService)
- Calculates text similarity
- Returns probability of duplicate
- Links reports if duplicate

### 6. Priority Agent
- Calculates weighted priority score
- Generates human-readable explanation
- Returns LOW/MEDIUM/HIGH/CRITICAL

### 7. Routing Agent
- Combines category + AI classification
- Checks department availability
- Returns department + confidence + reason

### 8. Action Agent
- Creates CivicTask via MCP Civic Server
- Notifies department via MCP Notification Server
- Records all actions in audit log

### 9. Monitoring Agent
- Sets SLA based on priority
- Registers periodic check
- Triggers escalation when SLA breached

### 10. Resolution Verification Agent
- Receives before + after images
- Calls multimodal AI for comparison
- Returns resolution confidence
- Updates complaint status

## Graph Flow

```
START
  ↓
intake_agent
  ↓
vision_agent (if image present)
  ↓
location_agent
  ↓
validation_agent
  ↓ (conditional)
  ├─ is_valid=False → human_review_node → END
  └─ is_valid=True
       ↓
     duplicate_agent
       ↓ (conditional)
       ├─ is_duplicate=True → link_duplicate → END
       └─ is_duplicate=False
            ↓
          priority_agent
            ↓
          routing_agent
            ↓ (conditional)
            ├─ confidence<0.70 → human_approval_gate
            └─ confidence≥0.70
                 ↓
               action_agent
                 ↓
               monitoring_agent
                 ↓
               END
```

## Human-in-the-Loop Gates

The graph pauses at these nodes pending external approval:

1. **validation_failure** — officer reviews flagged report
2. **low_confidence_routing** — admin approves routing decision
3. **critical_incident** — admin approves before action
4. **resolution_disputed** — officer reviews AI resolution verdict

## Observability

Every agent logs to `agent_trace`:

```json
{
  "agent": "priority_agent",
  "started_at": "2026-01-01T10:00:00Z",
  "completed_at": "2026-01-01T10:00:01Z",
  "status": "success",
  "output_summary": "Priority: HIGH (score=0.82)"
}
```

This trace is displayed on the complaint detail page.
