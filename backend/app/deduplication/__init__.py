"""Offline civic incident duplicate detection primitives."""

from app.deduplication.engine import (
    CandidateIncident,
    MatchDecision,
    MatchResult,
    ReportEvidence,
    Thresholds,
    match_report,
    score_candidate,
)

__all__ = [
    "CandidateIncident", "MatchDecision", "MatchResult", "ReportEvidence",
    "Thresholds", "match_report", "score_candidate",
]
