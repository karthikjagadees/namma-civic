"""Build the labeled synthetic pair file and report held-out resolver metrics."""

from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.deduplication.evaluation import evaluate_thresholds, write_synthetic_dataset


def main() -> None:
    """Write synthetic data and print thresholds plus held-out evaluation metrics."""
    backend_dir = BACKEND_DIR
    dataset_path = backend_dir / "data" / "synthetic_duplicate_pairs.json"
    pair_count = write_synthetic_dataset(dataset_path)
    report = evaluate_thresholds()
    output = asdict(report)
    output["dataset_path"] = str(dataset_path.relative_to(backend_dir))
    output["dataset_count_written"] = pair_count
    print(json.dumps(output, indent=2, default=lambda value: value.value if hasattr(value, "value") else str(value)))


if __name__ == "__main__":
    main()
