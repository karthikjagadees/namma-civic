"""Conservative threshold recommendations from adjudicated officer labels."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from app.deduplication.engine import Thresholds


@dataclass(frozen=True)
class LabelMetrics:
    """Binary precision, recall, and F1 at one proposed score threshold."""

    precision: float
    recall: float
    f1: float


@dataclass(frozen=True)
class ThresholdRecommendation:
    """A report-only recommendation; it never changes active engine settings."""

    current: Thresholds
    proposed: Thresholds
    auto_metrics: LabelMetrics
    review_metrics: LabelMetrics
    labeled_pair_count: int
    applied: bool = False


def recommend_thresholds(
    labels: Sequence[tuple[float, bool]], current: Thresholds = Thresholds(),
) -> ThresholdRecommendation:
    """Return a precision-oriented auto threshold and high-recall review threshold.

    Input labels are officer-adjudicated (score, duplicate) pairs. This function
    is intentionally a report-only calibration step; applying a recommendation
    requires a separate reviewed code/configuration change.
    """
    clean = [(min(1.0, max(0.0, float(score))), bool(label)) for score, label in labels]
    if not clean:
        return ThresholdRecommendation(current, current, _metrics([], 1.0), _metrics([], 0.58), 0)
    thresholds = sorted({0.0, 1.0, *(score for score, _ in clean)})
    auto_candidates = []
    for threshold in thresholds:
        metrics = _metrics(clean, threshold)
        if metrics.precision >= 0.95:
            auto_candidates.append((metrics.f1, metrics.precision, metrics.recall, threshold))
    if auto_candidates:
        auto_threshold = max(auto_candidates)[3]
    else:
        auto_threshold = max((
            (_metrics(clean, threshold).precision, _metrics(clean, threshold).f1, threshold)
            for threshold in thresholds
        ))[2]
    review_candidates = [
        threshold for threshold in thresholds
        if threshold <= auto_threshold and _metrics(clean, threshold).recall >= 0.98
    ]
    review_threshold = min(review_candidates) if review_candidates else min(auto_threshold, current.review)
    proposed = Thresholds(auto_link=auto_threshold, review=review_threshold)
    return ThresholdRecommendation(
        current=current,
        proposed=proposed,
        auto_metrics=_metrics(clean, auto_threshold),
        review_metrics=_metrics(clean, review_threshold),
        labeled_pair_count=len(clean),
    )


def _metrics(labels: Sequence[tuple[float, bool]], threshold: float) -> LabelMetrics:
    """Calculate binary metrics without hiding small sample sizes."""
    tp = sum(label and score >= threshold for score, label in labels)
    fp = sum((not label) and score >= threshold for score, label in labels)
    fn = sum(label and score < threshold for score, label in labels)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return LabelMetrics(precision, recall, f1)
