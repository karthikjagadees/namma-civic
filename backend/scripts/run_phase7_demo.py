"""Run the offline Phase 7 synthetic verification demo on a seeded test DB."""
from __future__ import annotations

import os
import subprocess
import sys


def main() -> int:
    """Run the deterministic pytest scenario that initializes its own DB."""
    environment = os.environ.copy()
    environment.update({
        "AI_MODE": "mock",
        "AI_PROVIDER": "mock",
        "MCP_MODE": "mock",
        "DEBUG": "true",
    })
    command = [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_phase7_verification.py",
        "-k",
        "five_synthetic_reports",
        "-q",
        "-s",
    ]
    completed = subprocess.run(command, env=environment, check=False)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
