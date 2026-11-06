"""Reproducible, explicitly synthetic threshold calibration and test evaluation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from typing import Mapping, Sequence

from app.deduplication.engine import (
    CandidateIncident,
    ReportEvidence,
    SIGNAL_WEIGHTS,
    Thresholds,
    score_candidate,
)


@dataclass(frozen=True)
class SyntheticPair:
    """One generated report/candidate pair and its synthetic binary label."""

    pair_id: str
    report: ReportEvidence
    candidate: CandidateIncident
    label: bool
    scenario: str
    dataset_kind: str = "synthetic"


@dataclass(frozen=True)
class BinaryMetrics:
    """Precision, recall, F1, and confusion counts for a binary decision."""

    precision: float
    recall: float
    f1: float
    true_positive: int
    false_positive: int
    false_negative: int
    true_negative: int


@dataclass(frozen=True)
class EvaluationReport:
    """Split sizes, calibrated thresholds, held-out metrics, and ablations."""

    dataset_kind: str
    total_count: int
    calibration_count: int
    test_count: int
    selected_thresholds: Thresholds
    per_signal_test_metrics: Mapping[str, BinaryMetrics]
    fused_test_metrics: BinaryMetrics
    review_candidate_test_metrics: BinaryMetrics
    ablation_test_metrics: Mapping[str, BinaryMetrics]


CHANNELS = ("web", "mobile", "voice", "whatsapp")
NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
_POSITIVE_TEXTS = (
    "Deep pothole near the school entrance",
    "Road crater outside school gate",
    "Large gaddha on School Road by the entrance",
    "Big road hole near the school entry",
    "School gate ke paas bada pothole",
)
_NEGATIVE_TEXTS = (
    "Overflowing trash bins beside the bus shelter",
    "Streetlight is dark at the corner junction",
    "Water pipe is leaking across the footpath",
    "Drain cover is missing near the market",
    "Illegal stall blocks the pedestrian path",
)
_SAME_PHASH = "0000000000000000"
_DIFFERENT_PHASH = "ffffffffffffffff"


def _point(latitude: float, longitude: float, offset_m: float) -> tuple[float, float]:
    """Move east by an approximate number of meters for generated pairs."""
    return latitude, longitude + offset_m / (111_320.0 * max(0.2, abs(__import__("math").cos(__import__("math").radians(latitude)))))


def _pair(index: int, positive: bool, scenario: str) -> SyntheticPair:
    """Build one deterministic synthetic pair for a labeled scenario."""
    lat = 12.97 + (index % 13) * 0.001
    lon = 77.59 + (index % 17) * 0.001
    category = "pothole"
    candidate_category = "pothole"
    if positive:
        text = _POSITIVE_TEXTS[index % len(_POSITIVE_TEXTS)]
        candidate_text = _POSITIVE_TEXTS[(index + 2) % len(_POSITIVE_TEXTS)]
        delta = 4.0 + (index % 7) * 2.0
        report_hash = candidate_hash = _SAME_PHASH if index % 4 != 0 else None
        candidate_category = "pothole" if index % 8 else "drainage"
        created = NOW - timedelta(days=1 + index % 20)
    else:
        if scenario == "same_street_other_category":
            category, candidate_category = "garbage", "pothole"
            text, candidate_text = _NEGATIVE_TEXTS[index % 5], "Large pothole at this corner"
            delta = 12.0
        elif scenario == "same_issue_distant_time":
            category = candidate_category = "pothole"
            text = candidate_text = _POSITIVE_TEXTS[index % 5]
            delta = 850.0
        else:
            category = candidate_category = "pothole"
            text, candidate_text = _NEGATIVE_TEXTS[index % 5], _POSITIVE_TEXTS[index % 5]
            delta = 18.0 + (index % 10) * 2.0
        report_hash, candidate_hash = None, _DIFFERENT_PHASH if index % 3 else None
        created = NOW - timedelta(days=1 + index % 35)

    report_lat, report_lon = _point(lat, lon, delta)
    candidate_lat, candidate_lon = lat, lon
    channel = CHANNELS[index % len(CHANNELS)]
    report = ReportEvidence(
        report_id=f"synthetic-report-{index:04d}",
        text=text,
        category=category,
        latitude=report_lat,
        longitude=report_lon,
        location_accuracy_m=5.0 if index % 3 else 15.0,
        address="School Road" if positive else ("Market Road" if scenario == "same_issue_distant_time" else "Main Street"),
        landmark="School entrance" if positive else "Market corner",
        photo_hashes=(report_hash,) if report_hash else (),
        channel=channel,
        reported_at=NOW,
    )
    candidate = CandidateIncident(
        incident_id=f"synthetic-incident-{index:04d}",
        title=candidate_text[:80],
        report_texts=(candidate_text,),
        category=candidate_category,
        status="open",
        latitude=candidate_lat,
        longitude=candidate_lon,
        location_accuracy_m=8.0,
        address="School Road" if positive else ("Market Road" if scenario == "same_issue_distant_time" else "Main Street"),
        landmark="School entrance" if positive else "Market corner",
        photo_hashes=(candidate_hash,) if candidate_hash else (),
        created_at=created,
        last_reported_at=created,
    )
    return SyntheticPair(
        pair_id=f"pair-{index:04d}", report=report, candidate=candidate,
        label=positive, scenario=scenario,
    )


def build_synthetic_dataset() -> tuple[SyntheticPair, ...]:
    """Return 200 synthetic labeled pairs with wording variation and hard negatives."""
    pairs: list[SyntheticPair] = []
    for index in range(100):
        pairs.append(_pair(index, True, "same_issue_different_wording_channel_photo"))
    negative_scenarios = (
        "nearby_different_pothole",
        "same_street_other_category",
        "same_issue_distant_time",
        "nearby_same_category_different_issue",
    )
    for index in range(100):
        scenario = negative_scenarios[index % len(negative_scenarios)]
        pairs.append(_pair(index + 100, False, scenario))
    return tuple(pairs)


def write_synthetic_dataset(path: str | Path) -> int:
    """Write the reproducible labeled synthetic pairs as JSON and return its size."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for pair in build_synthetic_dataset():
        rows.append({
            "pair_id": pair.pair_id,
            "dataset_kind": pair.dataset_kind,
            "label_duplicate": pair.label,
            "scenario": pair.scenario,
            "report": asdict(pair.report),
            "candidate": asdict(pair.candidate),
        })
    destination.write_text(json.dumps(rows, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return len(rows)


def _partition(dataset: Sequence[SyntheticPair]) -> tuple[list[SyntheticPair], list[SyntheticPair]]:
    """Deterministically split each class 80/20 into calibration and held-out test."""
    buckets = {"calibration": [], "test": []}
    by_class: dict[bool, list[SyntheticPair]] = {True: [], False: []}
    for pair in dataset:
        by_class[pair.label].append(pair)
    for label_pairs in by_class.values():
        label_pairs.sort(key=lambda pair: hashlib.sha256(pair.pair_id.encode()).hexdigest())
        for index, pair in enumerate(label_pairs):
            remainder = index % 5
            split = "calibration" if remainder != 4 else "test"
            buckets[split].append(pair)
    return buckets["calibration"], buckets["test"]


def _metrics(labels: Sequence[bool], predictions: Sequence[bool]) -> BinaryMetrics:
    """Compute unrounded classification metrics and confusion counts."""
    tp = sum(label and prediction for label, prediction in zip(labels, predictions))
    fp = sum((not label) and prediction for label, prediction in zip(labels, predictions))
    fn = sum(label and (not prediction) for label, prediction in zip(labels, predictions))
    tn = sum((not label) and (not prediction) for label, prediction in zip(labels, predictions))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return BinaryMetrics(precision, recall, f1, tp, fp, fn, tn)


def _fused_score(pair: SyntheticPair, omit: str | None = None) -> float:
    score = score_candidate(pair.report, pair.candidate)
    signals = score.signals
    weights = {name: weight for name, weight in SIGNAL_WEIGHTS.items() if name != omit and signals[name] is not None}
    total = sum(weights.values())
    return sum(weights[name] * float(signals[name]) for name in weights) / total if total else 0.0


def _best_threshold(
    pairs: Sequence[SyntheticPair],
    scores: Mapping[str, float],
    *,
    minimum_precision: float = 0.90,
    minimum_recall: float | None = None,
    minimum_threshold: float = 0.0,
) -> float:
    candidates = [step / 100 for step in range(int(minimum_threshold * 100), 100)]
    evaluated = []
    labels = [pair.label for pair in pairs]
    for threshold in candidates:
        metrics = _metrics(labels, [scores[pair.pair_id] >= threshold for pair in pairs])
        if metrics.precision >= minimum_precision and (minimum_recall is None or metrics.recall >= minimum_recall):
            evaluated.append((metrics.f1, metrics.precision, metrics.recall, threshold))
    if evaluated:
        return max(evaluated)[3]
    fallback = []
    for threshold in candidates:
        metrics = _metrics(labels, [scores[pair.pair_id] >= threshold for pair in pairs])
        fallback.append((metrics.precision, metrics.f1, threshold))
    return max(fallback)[2]


def _evaluate_signal(
    calibration: Sequence[SyntheticPair],
    test: Sequence[SyntheticPair],
    signal_name: str,
) -> BinaryMetrics:
    calibration_scores = {pair.pair_id: score_candidate(pair.report, pair.candidate).signals[signal_name] or 0.0 for pair in calibration}
    test_scores = {pair.pair_id: score_candidate(pair.report, pair.candidate).signals[signal_name] or 0.0 for pair in test}
    threshold = _best_threshold(calibration, calibration_scores)
    return _metrics([pair.label for pair in test], [test_scores[pair.pair_id] >= threshold for pair in test])


def evaluate_thresholds(dataset: Sequence[SyntheticPair] | None = None) -> EvaluationReport:
    """Select thresholds on calibration data and report untouched held-out metrics."""
    pairs = tuple(dataset or build_synthetic_dataset())
    if len(pairs) < 150 or any(pair.dataset_kind != "synthetic" for pair in pairs):
        raise ValueError("Evaluation requires at least 150 explicitly synthetic labeled pairs")
    calibration, test = _partition(pairs)
    calibration_scores = {pair.pair_id: _fused_score(pair) for pair in calibration}
    test_scores = {pair.pair_id: _fused_score(pair) for pair in test}
    review_threshold = _best_threshold(
        calibration,
        calibration_scores,
        minimum_precision=0.0,
        minimum_recall=0.98,
        minimum_threshold=0.20,
    )
    auto_threshold = _best_threshold(
        calibration,
        calibration_scores,
        minimum_precision=0.95,
        minimum_threshold=review_threshold + 0.01,
    )
    thresholds = Thresholds(auto_link=auto_threshold, review=review_threshold)
    fused_metrics = _metrics([pair.label for pair in test], [test_scores[pair.pair_id] >= auto_threshold for pair in test])
    review_metrics = _metrics([pair.label for pair in test], [test_scores[pair.pair_id] >= review_threshold for pair in test])

    signal_names = tuple(SIGNAL_WEIGHTS)
    per_signal = {name: _evaluate_signal(calibration, test, name) for name in signal_names}
    per_signal["fused"] = fused_metrics
    ablations: dict[str, BinaryMetrics] = {}
    for omitted in signal_names:
        calibration_without = {pair.pair_id: _fused_score(pair, omitted) for pair in calibration}
        test_without = {pair.pair_id: _fused_score(pair, omitted) for pair in test}
        threshold_without = _best_threshold(calibration, calibration_without, minimum_precision=0.95)
        ablations[f"without_{omitted}"] = _metrics(
            [pair.label for pair in test],
            [test_without[pair.pair_id] >= threshold_without for pair in test],
        )
    return EvaluationReport(
        dataset_kind="synthetic",
        total_count=len(pairs),
        calibration_count=len(calibration),
        test_count=len(test),
        selected_thresholds=thresholds,
        per_signal_test_metrics=per_signal,
        fused_test_metrics=fused_metrics,
        review_candidate_test_metrics=review_metrics,
        ablation_test_metrics=ablations,
    )
