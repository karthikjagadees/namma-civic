"""
Namma Civic — LangGraph Multi-Agent Orchestration Graph
Compiles state graph, conditional edges, checkpointer persistence, and human-in-the-loop interruption.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.agents.nodes import (
    action_node,
    approval_node,
    deduplication_node,
    intake_node,
    monitoring_node,
    priority_node,
    resolution_verification_node,
    routing_node,
    validation_node,
    vision_node,
)
from app.agents.state import CivicActionState

logger = logging.getLogger("namma-civic.agent.graph")


def route_after_validation(state: CivicActionState) -> str:
    """Route to deduplication if valid, or route to human approval if suspected spam."""
    validation = state.get("validation_result", {})
    if not validation.get("is_valid", True):
        logger.info("[RoutingEdge] Validation failed. Diverting to approval.")
        return "approval"
    return "deduplication"


def route_after_routing(state: CivicActionState) -> str:
    """Route to approval if policy flagged HITL, else auto-dispatch action."""
    if state.get("requires_human_approval", False):
        logger.info(f"[RoutingEdge] HITL Triggered: {state.get('approval_reason')}. Routing to approval.")
        return "approval"
    logger.info("[RoutingEdge] Policy clear. Proceeding directly to autonomous action dispatch.")
    return "action"


def route_after_approval(state: CivicActionState) -> str:
    """If awaiting approval, pause execution at END. If decision reached, route to action."""
    if state.get("is_awaiting_approval", False):
        logger.info("[RoutingEdge] Pausing graph execution at approval gate for human review.")
        return END
    return "action"


def build_civic_action_graph(checkpointer: Any = None):
    """
    Constructs and compiles the multi-agent orchestration graph with persistence.
    """
    workflow = StateGraph(CivicActionState)

    # Register Nodes
    workflow.add_node("intake", intake_node)
    workflow.add_node("vision", vision_node)
    workflow.add_node("validation", validation_node)
    workflow.add_node("deduplication", deduplication_node)
    workflow.add_node("priority", priority_node)
    workflow.add_node("routing", routing_node)
    workflow.add_node("approval", approval_node)
    workflow.add_node("action", action_node)
    workflow.add_node("monitoring", monitoring_node)
    workflow.add_node("resolution_verification", resolution_verification_node)

    # Linear Start
    workflow.add_edge(START, "intake")
    workflow.add_edge("intake", "vision")
    workflow.add_edge("vision", "validation")

    # Conditional Branch 1: Validation
    workflow.add_conditional_edges(
        "validation",
        route_after_validation,
        {
            "deduplication": "deduplication",
            "approval": "approval",
        },
    )

    # Branch 2: Deduplication to Routing
    workflow.add_edge("deduplication", "routing")
    workflow.add_edge("routing", "priority")

    # Conditional Branch 3: Routing (HITL vs Auto-Action)
    workflow.add_conditional_edges(
        "priority",
        route_after_routing,
        {
            "approval": "approval",
            "action": "action",
        },
    )

    # Conditional Branch 4: Approval (Pause vs Dispatch)
    workflow.add_conditional_edges(
        "approval",
        route_after_approval,
        {
            "action": "action",
            END: END,
        },
    )

    # Action concludes
    workflow.add_edge("action", "monitoring")
    workflow.add_edge("monitoring", "resolution_verification")
    workflow.add_edge("resolution_verification", END)

    if checkpointer is None:
        checkpointer = MemorySaver()

    return workflow.compile(checkpointer=checkpointer)


# Singleton compiled graph instance with persistent memory saver
global_checkpointer = MemorySaver()
civic_action_graph = build_civic_action_graph(checkpointer=global_checkpointer)
